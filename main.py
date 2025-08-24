import streamlit as st
import pandas as pd
import json
import sqlite3
import os
from typing import Dict, List, Any, Optional
import math

# -------------------------
# Конфигурация и настройки
# -------------------------

# Настройка страницы
st.set_page_config(
    page_title="Protein API Server",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Скрываем стандартные элементы Streamlit
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Функции для работы с данными
# -------------------------

def get_database_connection():
    """Создает подключение к базе данных"""
    try:
        # Путь к базе данных (может быть изменен)
        db_path = os.getenv("DATABASE_PATH", "metabolome.db")
        
        # Проверяем существование файла
        if not os.path.exists(db_path):
            st.warning(f"База данных не найдена по пути: {db_path}")
            st.info("Убедитесь, что файл БД загружен в репозиторий")
            return None
            
        return sqlite3.connect(db_path)
    except Exception as e:
        st.error(f"Ошибка подключения к БД: {e}")
        return None

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
            # Создаем условия поиска для всех текстовых полей
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
            "results": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size),
            "table": table_name,
            "columns": columns
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def search_metabolites(query: str = None, mass: float = None, tol_ppm: int = 10, 
                       page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Поиск метаболитов (адаптивная версия)"""
    try:
        # Сначала пробуем найти таблицу metabolites
        result = search_table("metabolites", query, page, page_size)
        if "error" not in result:
            return result
        
        # Если таблицы нет, ищем похожие таблицы
        db_info = get_database_info()
        if "error" in db_info:
            return db_info
        
        # Ищем таблицы, которые могут содержать метаболиты
        metabolite_tables = [t for t in db_info["tables"] if "metabolite" in t.lower() or "compound" in t.lower()]
        
        if metabolite_tables:
            # Используем первую найденную таблицу
            return search_table(metabolite_tables[0], query, page, page_size)
        else:
            return {"error": "No metabolite tables found", "available_tables": db_info["tables"]}
            
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def search_enzymes(query: str = None, organism_type: str = None,
                   page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Поиск ферментов (адаптивная версия)"""
    try:
        # Сначала пробуем найти таблицу enzymes
        result = search_table("enzymes", query, page, page_size)
        if "error" not in result:
            return result
        
        # Если таблицы нет, ищем похожие таблицы
        db_info = get_database_info()
        if "error" in db_info:
            return db_info
        
        # Ищем таблицы, которые могут содержать ферменты
        enzyme_tables = [t for t in db_info["tables"] if "enzyme" in t.lower() or "protein" in t.lower()]
        
        if enzyme_tables:
            # Используем первую найденную таблицу
            return search_table(enzyme_tables[0], query, page, page_size)
        else:
            return {"error": "No enzyme tables found", "available_tables": db_info["tables"]}
            
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

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

def get_health_status() -> Dict[str, Any]:
    """Статус API и статистика"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
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
            "database_info": db_info,
            "table_counts": table_counts,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def annotate_csv_data(file_content: bytes, mz_column: str, tol_ppm: int = 10) -> Dict[str, Any]:
    """Аннотация CSV данных"""
    try:
        # Читаем CSV
        df = pd.read_csv(file_content)
        
        if mz_column not in df.columns:
            return {"error": f"Column '{mz_column}' not found in CSV"}
        
        # Получаем массы
        mz_values = df[mz_column].astype(float).tolist()
        
        results = []
        for mz in mz_values:
            # Ищем метаболиты для каждой массы
            search_result = search_metabolites(query=str(mz), page_size=5)
            
            if "error" not in search_result and search_result.get("results"):
                best_match = search_result["results"][0]
                candidates = [m.get("name", str(m)) for m in search_result["results"]]
                
                results.append({
                    "mz": mz,
                    "candidates": candidates,
                    "best_match": best_match
                })
            else:
                results.append({
                    "mz": mz,
                    "candidates": [],
                    "best_match": None
                })
        
        return {
            "items": results,
            "total_annotated": len(results),
            "tolerance_ppm": tol_ppm
        }
        
    except Exception as e:
        return {"error": f"Annotation failed: {str(e)}"}

# -------------------------
# Основной интерфейс API
# -------------------------

st.title("🧬 Metabolome API Server")
st.markdown("**API сервер для работы с базой данных metabolome.db**")

# Боковая панель для API тестирования
with st.sidebar:
    st.header("🔧 API Testing")
    
    # Выбор эндпоинта
    endpoint = st.selectbox(
        "Выберите эндпоинт для тестирования:",
        ["/health", "/metabolites/search", "/enzymes/search", "/annotate/csv"]
    )
    
    if endpoint == "/health":
        st.subheader("🏥 Health Check")
        if st.button("Проверить статус"):
            result = get_health_status()
            st.json(result)
    
    elif endpoint == "/metabolites/search":
        st.subheader("🔍 Универсальный поиск")
        
        # Получаем список доступных таблиц
        db_info = get_database_info()
        if "error" not in db_info:
            available_tables = db_info["tables"]
            selected_table = st.selectbox("Выберите таблицу:", available_tables)
        else:
            st.error("Не удалось получить информацию о таблицах")
            st.stop()
        
        query = st.text_input("Запрос:", placeholder="глюкоза, C6H12O6")
        page = st.number_input("Страница:", min_value=1, value=1)
        page_size = st.selectbox("Размер страницы:", [25, 50, 100, 200])
        
        if st.button("🔍 Найти"):
            result = search_table(selected_table, query, page, page_size)
            st.json(result)
    
    elif endpoint == "/enzymes/search":
        st.subheader("🧪 Поиск по таблицам")
        
        query = st.text_input("Запрос:", placeholder="Ribulose, dehydrogenase")
        organism_type = st.selectbox("Тип организма:", ["Все", "plant", "animal", "bacteria", "fungi"])
        page = st.number_input("Страница:", min_value=1, value=1)
        page_size = st.selectbox("Размер страницы:", [25, 50, 100, 200])
        
        if st.button("🔍 Найти"):
            result = search_enzymes(
                query=query, organism_type=organism_type,
                page=page, page_size=page_size
            )
            st.json(result)
    
    elif endpoint == "/annotate/csv":
        st.subheader("📁 Аннотация CSV")
        
        uploaded_file = st.file_uploader("Загрузите CSV файл", type=['csv'])
        if uploaded_file:
            mz_column = st.selectbox("Столбец с массами:", ["mz", "mass", "m/z"])
            tol_ppm = st.slider("Допуск (ppm):", 1, 100, 10)
            
            if st.button("🔬 Аннотировать"):
                result = annotate_csv_data(
                    uploaded_file.getvalue(), mz_column, tol_ppm
                )
                st.json(result)

# -------------------------
# Основной контент
# -------------------------

# Статус API
st.header("📊 Статус API")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏥 Проверить здоровье API"):
        health = get_health_status()
        if health["status"] == "healthy":
            st.success("✅ API здоров")
            
            # Показываем информацию о таблицах
            if "table_counts" in health:
                st.write("**Количество записей в таблицах:**")
                for table, count in health["table_counts"].items():
                    st.write(f"• {table}: {count}")
        else:
            st.error(f"❌ API нездоров: {health.get('error', 'Unknown error')}")
    
    # Добавляем кнопку для просмотра структуры БД
    if st.button("📊 Структура БД"):
        db_info = get_database_info()
        if "error" not in db_info:
            st.success("✅ Структура БД получена")
            st.json(db_info)
        else:
            st.error(f"❌ Ошибка: {db_info['error']}")

with col2:
    st.info("🔍 **Доступные эндпоинты:**")
    st.write("• `/health` - статус API")
    st.write("• `/metabolites/search` - поиск по любой таблице")
    st.write("• `/enzymes/search` - поиск по любой таблице")
    st.write("• `/annotate/csv` - аннотация CSV")

with col3:
    st.info("📚 **Документация:**")
    st.write("Используйте боковую панель для тестирования API")
    st.write("Все ответы в формате JSON")
    st.write("Поддерживается пагинация")

# Примеры использования
st.header("💡 Примеры использования API")

tab1, tab2, tab3 = st.tabs(["🔍 Универсальный поиск", "🧪 Поиск по таблицам", "📁 Аннотация CSV"])

with tab1:
    st.markdown("""
    **Универсальный поиск по любой таблице:**
    ```python
    import requests
    
    # Поиск по названию/тексту
    response = requests.get("https://your-app.streamlit.app/metabolites/search", 
                          params={"table": "your_table", "q": "search_term", "page_size": 10})
    results = response.json()
    ```
    
    **Параметры поиска:**
    - `table` - название таблицы
    - `q` - поисковый запрос
    - `page` - номер страницы
    - `page_size` - размер страницы
    """)

with tab2:
    st.markdown("""
    **Поиск по структуре таблиц:**
    ```python
    # Получение информации о структуре БД
    response = requests.get("https://your-app.streamlit.app/health")
    db_info = response.json()
    
    # Поиск по конкретной таблице
    response = requests.get("https://your-app.streamlit.app/enzymes/search", 
                          params={"table": "metabolites", "q": "glucose"})
    results = response.json()
    ```
    """)

with tab3:
    st.markdown("""
    **Аннотация CSV файла:**
    ```python
    with open("data.csv", "rb") as f:
        files = {"file": f}
        data = {"mz_column": "mz", "tol_ppm": 10}
        response = requests.post("https://your-app.streamlit.app/annotate/csv", 
                               files=files, data=data)
    ```
    
    **Примечание:** Аннотация работает с любыми таблицами, содержащими текстовые данные
    """)

# Информация о развертывании
st.header("🚀 Информация о развертывании")
st.markdown("""
**Этот Streamlit сервер работает как API для:**
- Универсального поиска по любым таблицам в базе данных
- Получения информации о структуре базы данных
- Аннотации CSV файлов с данными

**Для использования в других приложениях:**
1. Получите URL вашего Streamlit приложения
2. Используйте его как базовый URL для API
3. Отправляйте HTTP запросы на соответствующие эндпоинты

**Пример базового URL:**
```
https://your-app-name.streamlit.app
```
""")

# Футер
st.markdown("---")
st.markdown("🧬 **Metabolome API Server** - API сервер на базе Streamlit")

