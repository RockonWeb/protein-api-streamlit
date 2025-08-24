import streamlit as st
import pandas as pd
import json
import sqlite3
import os
import requests
import io
from typing import Dict, List, Any, Optional
import math
import plotly.express as px

# -------------------------
# Конфигурация и настройки
# -------------------------

# Настройка страницы
st.set_page_config(
    page_title="Метаболомный справочник + API",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Скрываем стандартные элементы Streamlit
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Стили для карточек */
    .kpi-card {
        background: linear-gradient(135deg, #0ea5e9 0%, #22d3ee 100%);
        color: #ffffff;
        padding: 14px 16px;
        border-radius: 12px;
        box-shadow: 0 6px 18px rgba(2,132,199,0.25);
        border: 1px solid rgba(255,255,255,0.15);
    }
    .kpi-title {
        font-size: 13px;
        letter-spacing: 0.4px;
        opacity: 0.95;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 12px;
        opacity: 0.9;
        margin-top: 6px;
    }
    
    .card {
        background: #ffffff;
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.07);
        box-shadow: 0 6px 18px rgba(0,0,0,0.06);
        padding: 14px 14px 12px 14px;
        margin-bottom: 12px;
    }
    .card-title {
        font-size: 16px;
        font-weight: 700;
        margin: 0 0 6px 0;
    }
    .card-subtitle { font-size: 12px; color: #475569; margin-bottom: 10px; }
    .pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 999px;
        background: #f1f5f9;
        color: #0f172a;
        font-size: 11px;
        border: 1px solid #e2e8f0;
        margin-right: 6px;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# API функции
# -------------------------

def get_database_connection():
    """Создает подключение к базе данных"""
    try:
        # Путь к базе данных (может быть изменен)
        db_path = os.getenv("DATABASE_PATH", "metabolome.db")
        
        # Проверяем существование файла
        if not os.path.exists(db_path):
            return None
            
        return sqlite3.connect(db_path)
    except Exception as e:
        return None

def get_database_info() -> Dict[str, Any]:
    """Получает информацию о структуре базы данных"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        # Получаем список всех таблиц
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Получаем структуру каждой таблицы
        table_info = {}
        for table in tables:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
            table_info[table] = columns
        
        conn.close()
        
        return {
            "tables": tables,
            "table_info": table_info
        }
        
    except Exception as e:
        return {"error": f"Failed to get database info: {str(e)}"}

def get_health_status():
    """Проверяет статус подключения к БД и возвращает количество записей."""
    conn = get_database_connection()
    if conn is None:
        return {"status": "unhealthy", "message": "Database connection failed"}
    try:
        # Получаем информацию о таблицах
        db_info = get_database_info()
        if "error" in db_info:
            return {"status": "unhealthy", "error": db_info["error"]}
        
        # Подсчитываем записи в каждой таблице
        table_counts = {}
        for table in db_info["tables"]:
            try:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_counts[table] = count
            except Exception as e:
                table_counts[table] = f"Error: {str(e)}"
        
        conn.close()
        return {
            "status": "healthy",
            "message": "API is healthy",
            "database_info": db_info,
            "table_counts": table_counts,
            "timestamp": pd.Timestamp.now().isoformat()
        }
    except Exception as e:
        return {"status": "unhealthy", "message": f"Database query failed: {e}"}
    finally:
        if conn:
            conn.close()

def search_table(table_name: str, query: str = None, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Универсальный поиск по любой таблице"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        # Получаем информацию о структуре таблицы
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        if not columns:
            return {"error": f"Table {table_name} not found or empty"}
        
        # Базовый запрос
        base_query = f"SELECT * FROM {table_name} WHERE 1=1"
        params = []
        
        # Добавляем условия поиска по всем текстовым полям
        if query:
            # Создаем условия поиска для всех текстовых полях
            search_conditions = []
            for col in columns:
                search_conditions.append(f"{col} LIKE ?")
                params.append(f"%{query}%")
            
            if search_conditions:
                base_query += " AND (" + " OR ".join(search_conditions) + ")"
        
        # Подсчет общего количества
        count_query = f"SELECT COUNT(*) FROM ({base_query})"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Добавляем пагинацию
        base_query += " LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])
        
        # Выполняем основной запрос
        cursor = conn.execute(base_query, params)
        results = []
        
        for row in cursor.fetchall():
            # Создаем словарь с названиями колонок
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            results.append(row_dict)
        
        conn.close()
        
        return {
            "table": table_name,
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": results
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def search_metabolites(query: str = None, mass: float = None, tol_ppm: int = 10, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Поиск метаболитов с поддержкой поиска по массе"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        # Пытаемся найти таблицу metabolites
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%metabolite%'")
        metabolite_tables = [row[0] for row in cursor.fetchall()]
        
        if not metabolite_tables:
            # Если нет таблицы metabolites, используем универсальный поиск
            return search_table("metabolites", query, page, page_size)
        
        table_name = metabolite_tables[0]  # Берем первую найденную таблицу
        
        # Получаем структуру таблицы
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Базовый запрос
        base_query = f"SELECT * FROM {table_name} WHERE 1=1"
        params = []
        
        # Поиск по тексту
        if query:
            # Ищем поля для текстового поиска
            text_fields = [col for col in columns if any(keyword in col.lower() for keyword in ['name', 'formula', 'class'])]
            if text_fields:
                search_conditions = [f"{col} LIKE ?" for col in text_fields]
                base_query += " AND (" + " OR ".join(search_conditions) + ")"
                params.extend([f"%{query}%" for _ in text_fields])
        
        # Поиск по массе
        if mass:
            # Ищем поле для массы
            mass_fields = [col for col in columns if any(keyword in col.lower() for keyword in ['mass', 'weight', 'mz'])]
            if mass_fields:
                mass_field = mass_fields[0]
                tolerance = mass * tol_ppm / 1000000
                base_query += f" AND {mass_field} BETWEEN ? AND ?"
                params.extend([mass - tolerance, mass + tolerance])
        
        # Подсчет общего количества
        count_query = f"SELECT COUNT(*) FROM ({base_query})"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Добавляем пагинацию
        base_query += " LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])
        
        # Выполняем основной запрос
        cursor = conn.execute(base_query, params)
        results = []
        
        for row in cursor.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            results.append(row_dict)
        
        conn.close()
        
        return {
            "metabolites": results,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        return {"error": f"Metabolite search failed: {str(e)}"}

def search_enzymes(query: str = None, organism_type: str = None, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Поиск ферментов"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        # Пытаемся найти таблицу enzymes
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%enzyme%'")
        enzyme_tables = [row[0] for row in cursor.fetchall()]
        
        if not enzyme_tables:
            # Если нет таблицы enzymes, используем универсальный поиск
            return search_table("enzymes", query, page, page_size)
        
        table_name = enzyme_tables[0]  # Берем первую найденную таблицу
        
        # Получаем структуру таблицы
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Базовый запрос
        base_query = f"SELECT * FROM {table_name} WHERE 1=1"
        params = []
        
        # Поиск по тексту
        if query:
            # Ищем поля для текстового поиска
            text_fields = [col for col in columns if any(keyword in col.lower() for keyword in ['name', 'ec', 'family'])]
            if text_fields:
                search_conditions = [f"{col} LIKE ?" for col in text_fields]
                base_query += " AND (" + " OR ".join(search_conditions) + ")"
                params.extend([f"%{query}%" for _ in text_fields])
        
        # Фильтр по типу организма
        if organism_type and organism_type != "Все":
            # Ищем поле для типа организма
            org_fields = [col for col in columns if any(keyword in col.lower() for keyword in ['organism', 'type', 'species'])]
            if org_fields:
                org_field = org_fields[0]
                base_query += f" AND {org_field} LIKE ?"
                params.append(f"%{organism_type}%")
        
        # Подсчет общего количества
        count_query = f"SELECT COUNT(*) FROM ({base_query})"
        cursor = conn.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Добавляем пагинацию
        base_query += " LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])
        
        # Выполняем основной запрос
        cursor = conn.execute(base_query, params)
        results = []
        
        for row in cursor.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            results.append(row_dict)
        
        conn.close()
        
        return {
            "enzymes": results,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        return {"error": f"Enzyme search failed: {str(e)}"}

def annotate_csv_data(file_content: bytes, mz_column: str, tol_ppm: int = 10) -> Dict[str, Any]:
    """Аннотация CSV данных метаболитами"""
    try:
        # Читаем CSV
        df = pd.read_csv(io.BytesIO(file_content))
        
        if mz_column not in df.columns:
            return {"error": f"Column {mz_column} not found in CSV"}
        
        # Получаем массы
        mz_values = df[mz_column].astype(float).tolist()
        
        # Аннотируем каждую массу
        annotated_items = []
        for mz in mz_values:
            # Ищем метаболиты по массе
            metabolites = search_metabolites(mass=mz, tol_ppm=tol_ppm, page_size=5)
            
            if "error" not in metabolites and metabolites.get("metabolites"):
                candidates = [met.get("name", "Unknown") for met in metabolites["metabolites"]]
                best_match = metabolites["metabolites"][0] if metabolites["metabolites"] else None
            else:
                candidates = []
                best_match = None
            
            annotated_items.append({
                "mz": mz,
                "candidates": candidates,
                "best_match": best_match
            })
        
        return {
            "items": annotated_items,
            "total_annotated": len(annotated_items),
            "tolerance_ppm": tol_ppm
        }
        
    except Exception as e:
        return {"error": f"Annotation failed: {str(e)}"}

# -------------------------
# Проверка API режима
# -------------------------

def is_api_mode():
    """Проверяет, работает ли приложение в API режиме"""
    query_params = st.experimental_get_query_params()
    return "api" in query_params or "format" in query_params

def handle_api_request():
    """Обрабатывает API запросы и возвращает JSON"""
    query_params = st.experimental_get_query_params()
    
    # Определяем тип запроса
    api_type = query_params.get("api", [None])[0]
    format_type = query_params.get("format", ["json"])[0]
    
    if api_type == "health":
        result = get_health_status()
    elif api_type == "metabolites":
        query = query_params.get("q", [None])[0]
        mass = query_params.get("mass", [None])[0]
        tol_ppm = int(query_params.get("tol_ppm", [10])[0])
        page = int(query_params.get("page", [1])[0])
        page_size = int(query_params.get("page_size", [50])[0])
        
        if mass:
            mass = float(mass)
        result = search_metabolites(query, mass, tol_ppm, page, page_size)
    elif api_type == "enzymes":
        query = query_params.get("q", [None])[0]
        organism_type = query_params.get("organism_type", [None])[0]
        page = int(query_params.get("page", [1])[0])
        page_size = int(query_params.get("page_size", [50])[0])
        result = search_enzymes(query, organism_type, page, page_size)
    elif api_type == "annotate":
        # Для аннотации нужен POST запрос, но Streamlit поддерживает только GET
        # Поэтому показываем инструкцию
        result = {
            "error": "CSV annotation requires POST request. Use the UI interface instead."
        }
    else:
        result = {
            "error": "Unknown API endpoint",
            "available_endpoints": ["health", "metabolites", "enzymes", "annotate"]
        }
    
    # Возвращаем результат в нужном формате
    if format_type == "json":
        st.json(result)
    else:
        st.write(result)
    
    st.stop()

# -------------------------
# UI функции
# -------------------------

def render_kpi(label: str, value: str, sub: str = ""):
    """Рисует KPI-карточку"""
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-title">{label}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_metabolite_card(met: Dict[str, Any]):
    """Карточка метаболита"""
    name = met.get("name") or "Без названия"
    formula = met.get("formula") or "—"
    mass = met.get("exact_mass") or met.get("mass") or met.get("molecular_weight")
    mass_fmt = f"{mass:.6f} Da" if isinstance(mass, (int, float)) else "—"
    cls = met.get("class_name") or met.get("class") or "—"
    
    st.markdown(
        f"""
        <div class="card">
          <div class="card-title">{name}</div>
          <div class="card-subtitle">Формула: <b>{formula}</b> &nbsp;|&nbsp; Масса: <b>{mass_fmt}</b></div>
          <div><span class='pill'>{cls}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_enzyme_card(enzyme: Dict[str, Any]):
    """Карточка фермента"""
    name = enzyme.get("name") or enzyme.get("name_en") or "Без названия"
    ec = enzyme.get("ec_number") or enzyme.get("ec") or "—"
    org = enzyme.get("organism") or "—"
    fam = enzyme.get("family") or "—"
    
    st.markdown(
        f"""
        <div class="card">
          <div class="card-title">{name}</div>
          <div class="card-subtitle">EC: <b>{ec}</b> &nbsp;|&nbsp; Организм: <b>{org}</b></div>
          <div><span class='pill'>{fam}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------
# Главная логика приложения
# -------------------------

def main():
    # Проверяем, работает ли в API режиме
    if is_api_mode():
        handle_api_request()
        return
    
    # UI режим - показываем интерфейс
    st.title("🧬 Метаболомный справочник + API")
    st.markdown("**Универсальное приложение для поиска метаболитов, ферментов и API доступа**")
    
    # KPI панель
    health_status = get_health_status()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if health_status.get("status") == "healthy":
            total_metabolites = health_status.get("table_counts", {}).get("metabolites", 0)
            render_kpi("Метаболиты", str(total_metabolites), "в базе данных")
        else:
            render_kpi("Метаболиты", "—", "БД недоступна")
    
    with col2:
        if health_status.get("status") == "healthy":
            total_enzymes = health_status.get("table_counts", {}).get("enzymes", 0)
            render_kpi("Ферменты", str(total_enzymes), "в базе данных")
        else:
            render_kpi("Ферменты", "—", "БД недоступна")
    
    with col3:
        status = health_status.get("status", "unknown")
        status_ru = "онлайн" if status == "healthy" else "офлайн"
        render_kpi("Статус API", status_ru, "сервис /health")
    
    # Боковая панель
    st.sidebar.markdown("## 🔍 **Поиск**")
    
    # Переключатель типа поиска
    search_type = st.sidebar.radio(
        "Тип поиска",
        options=["🧬 Метаболиты", "🧪 Ферменты"],
        horizontal=True
    )
    
    # Форма поиска метаболитов
    if search_type == "🧬 Метаболиты":
        with st.sidebar.form("metabolite_search"):
            st.subheader("🔍 Поиск метаболитов")
            
            mode = st.radio("Режим поиска", ["По названию", "По массе"])
            
            if mode == "По названию":
                query = st.text_input("Название или формула", placeholder="глюкоза, C6H12O6")
                mass = None
            else:
                query = None
                mass = st.number_input("Масса (m/z)", min_value=0.0, step=0.001, format="%.6f")
            
            tolerance = st.slider("Допуск (ppm)", 1, 100, 10)
            page_size = st.selectbox("Размер страницы", [25, 50, 100])
            
            if st.form_submit_button("🔍 Найти"):
                results = search_metabolites(query, mass, tolerance, 1, page_size)
                if "error" not in results:
                    st.session_state.metabolite_results = results
                    st.session_state.search_type = "metabolites"
                else:
                    st.error(f"Ошибка поиска: {results['error']}")
    
    # Форма поиска ферментов
    else:
        with st.sidebar.form("enzyme_search"):
            st.subheader("🔍 Поиск ферментов")
            
            query = st.text_input("Название, EC номер", placeholder="Ribulose, 4.1.1.39")
            organism_type = st.selectbox("Тип организма", ["Все", "plant", "animal", "bacteria"])
            page_size = st.selectbox("Размер страницы", [25, 50, 100])
            
            if st.form_submit_button("🔍 Найти"):
                results = search_enzymes(query, organism_type, 1, page_size)
                if "error" not in results:
                    st.session_state.enzyme_results = results
                    st.session_state.search_type = "enzymes"
                else:
                    st.error(f"Ошибка поиска: {results['error']}")
    
    # Основной контент
    if st.session_state.get("search_type") == "metabolites" and st.session_state.get("metabolite_results"):
        results = st.session_state.metabolite_results
        st.header("📊 Результаты поиска метаболитов")
        st.success(f"✅ Найдено {results['total']} метаболитов")
        
        # Отображение результатов
        if results.get("metabolites"):
            cols = st.columns(3)
            for idx, met in enumerate(results["metabolites"]):
                with cols[idx % 3]:
                    render_metabolite_card(met)
    
    elif st.session_state.get("search_type") == "enzymes" and st.session_state.get("enzyme_results"):
        results = st.session_state.enzyme_results
        st.header("📊 Результаты поиска ферментов")
        st.success(f"✅ Найдено {results['total']} ферментов")
        
        # Отображение результатов
        if results.get("enzymes"):
            cols = st.columns(3)
            for idx, enzyme in enumerate(results["enzymes"]):
                with cols[idx % 3]:
                    render_enzyme_card(enzyme)
    
    # Вкладки
    tab1, tab2, tab3 = st.tabs(["🔍 Поиск", "📁 Аннотация CSV", "🔌 API"])
    
    with tab1:
        st.header("🔍 Поиск")
        st.markdown("""
        **Используйте боковую панель для поиска!**
        
        - **Метаболиты**: по названию, формуле или массе
        - **Ферменты**: по названию, EC номеру или организму
        """)
    
    with tab2:
        st.header("📁 Аннотация CSV")
        st.markdown("Загрузите CSV файл с пиками LC-MS для аннотации")
        
        uploaded_file = st.file_uploader("Выберите CSV файл", type=['csv'])
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.success(f"✅ Файл загружен: {len(df)} строк")
            st.dataframe(df.head())
            
            if len(df.columns) > 0:
                mass_column = st.selectbox("Столбец с массами:", df.columns)
                tolerance = st.slider("Допуск (ppm):", 1, 100, 10)
                
                if st.button("🔬 Аннотировать"):
                    with st.spinner("Выполняется аннотация..."):
                        results = annotate_csv_data(
                            uploaded_file.getvalue(),
                            mass_column,
                            tolerance
                        )
                        
                        if "error" not in results:
                            st.success("✅ Аннотация завершена!")
                            st.json(results)
                        else:
                            st.error(f"❌ Ошибка: {results['error']}")
    
    with tab3:
        st.header("🔌 API Endpoints")
        st.markdown("""
        **Доступные API эндпоинты:**
        
        - **`?api=health`** - статус API и информация о БД
        - **`?api=metabolites&q=глюкоза`** - поиск метаболитов
        - **`?api=enzymes&q=ribulose`** - поиск ферментов
        - **`?api=metabolites&mass=180.063&tol_ppm=10`** - поиск по массе
        
        **Примеры использования:**
        - `/metabolites/search?q=глюкоза&page_size=10`
        - `/enzymes/search?organism_type=plant`
        - `/health`
        """)
        
        # Тестирование API
        st.subheader("🧪 Тестирование API")
        test_endpoint = st.selectbox(
            "Выберите эндпоинт для тестирования:",
            ["health", "metabolites", "enzymes"]
        )
        
        if test_endpoint == "metabolites":
            test_query = st.text_input("Поисковый запрос:", "глюкоза")
            if st.button("Тестировать"):
                test_url = f"?api=metabolites&q={test_query}&format=json"
                st.info(f"API URL: {test_url}")
                st.markdown(f"[Открыть в API режиме]({test_url})")
        
        elif test_endpoint == "enzymes":
            test_query = st.text_input("Поисковый запрос:", "ribulose")
            if st.button("Тестировать"):
                test_url = f"?api=enzymes&q={test_query}&format=json"
                st.info(f"API URL: {test_url}")
                st.markdown(f"[Открыть в API режиме](test_url)")
        
        else:  # health
            if st.button("Тестировать"):
                test_url = "?api=health&format=json"
                st.info(f"API URL: {test_url}")
                st.markdown(f"[Открыть в API режиме]({test_url})")
    
    # Футер
    st.markdown("---")
    st.markdown("🧬 **Метаболомный справочник + API** - Универсальное приложение для биохимии")

if __name__ == "__main__":
    main()

