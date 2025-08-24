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
        db_path = os.getenv("DATABASE_PATH", "data/protein.db")
        return sqlite3.connect(db_path)
    except Exception as e:
        st.error(f"Ошибка подключения к БД: {e}")
        return None

def search_metabolites(query: str = None, mass: float = None, tol_ppm: int = 10, 
                       page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Поиск метаболитов"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        # Базовый запрос
        base_query = """
        SELECT id, name, formula, exact_mass, class_name, 
               hmdb_id, kegg_id, chebi_id, pubchem_cid
        FROM metabolites 
        WHERE 1=1
        """
        params = []
        
        # Добавляем условия поиска
        if query:
            base_query += " AND (name LIKE ? OR formula LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        
        if mass:
            # Поиск по массе с допуском
            tolerance = mass * tol_ppm / 1000000
            base_query += " AND exact_mass BETWEEN ? AND ?"
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
            results.append({
                "id": row[0],
                "name": row[1],
                "formula": row[2],
                "exact_mass": row[3],
                "class_name": row[4],
                "hmdb_id": row[5],
                "kegg_id": row[6],
                "chebi_id": row[7],
                "pubchem_cid": row[8]
            })
        
        conn.close()
        
        return {
            "metabolites": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size)
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def search_enzymes(query: str = None, organism_type: str = None,
                   page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """Поиск ферментов"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        # Базовый запрос
        base_query = """
        SELECT id, name, ec_number, organism, organism_type, family,
               molecular_weight, optimal_ph, optimal_temperature,
               subcellular_location, protein_name, gene_name, uniprot_id,
               description, tissue_specificity
        FROM enzymes 
        WHERE 1=1
        """
        params = []
        
        # Добавляем условия поиска
        if query:
            base_query += " AND (name LIKE ? OR ec_number LIKE ? OR organism LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
        
        if organism_type and organism_type != "Все":
            base_query += " AND organism_type = ?"
            params.append(organism_type)
        
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
            results.append({
                "id": row[0],
                "name": row[1],
                "ec_number": row[2],
                "organism": row[3],
                "organism_type": row[4],
                "family": row[5],
                "molecular_weight": row[6],
                "optimal_ph": row[7],
                "optimal_temperature": row[8],
                "subcellular_location": row[9],
                "protein_name": row[10],
                "gene_name": row[11],
                "uniprot_id": row[12],
                "description": row[13],
                "tissue_specificity": row[14]
            })
        
        conn.close()
        
        return {
            "enzymes": results,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size)
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}

def get_health_status() -> Dict[str, Any]:
    """Статус API и статистика"""
    try:
        conn = get_database_connection()
        if not conn:
            return {"status": "unhealthy", "error": "Database connection failed"}
        
        # Подсчет метаболитов
        cursor = conn.execute("SELECT COUNT(*) FROM metabolites")
        metabolites_count = cursor.fetchone()[0]
        
        # Подсчет ферментов
        cursor = conn.execute("SELECT COUNT(*) FROM enzymes")
        enzymes_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "healthy",
            "metabolites_count": metabolites_count,
            "enzymes_count": enzymes_count,
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
            search_result = search_metabolites(mass=mz, tol_ppm=tol_ppm, page_size=5)
            
            if "error" not in search_result and search_result["metabolites"]:
                best_match = search_result["metabolites"][0]
                candidates = [m["name"] for m in search_result["metabolites"]]
                
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

st.title("🧬 Protein API Server")
st.markdown("**API сервер для работы с метаболитами и ферментами**")

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
        st.subheader("🔍 Поиск метаболитов")
        
        search_type = st.radio("Тип поиска:", ["По названию/формуле", "По массе"])
        
        if search_type == "По названию/формуле":
            query = st.text_input("Запрос:", placeholder="глюкоза, C6H12O6")
            mass = None
        else:
            query = None
            mass = st.number_input("Масса (m/z):", min_value=0.0, value=180.063, format="%.6f")
        
        tol_ppm = st.slider("Допуск (ppm):", 1, 100, 10)
        page = st.number_input("Страница:", min_value=1, value=1)
        page_size = st.selectbox("Размер страницы:", [25, 50, 100, 200])
        
        if st.button("🔍 Найти"):
            result = search_metabolites(
                query=query, mass=mass, tol_ppm=tol_ppm,
                page=page, page_size=page_size
            )
            st.json(result)
    
    elif endpoint == "/enzymes/search":
        st.subheader("🧪 Поиск ферментов")
        
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
            st.success(f"✅ API здоров")
            st.metric("Метаболиты", health["metabolites_count"])
            st.metric("Ферменты", health["enzymes_count"])
        else:
            st.error(f"❌ API нездоров: {health.get('error', 'Unknown error')}")

with col2:
    st.info("🔍 **Доступные эндпоинты:**")
    st.write("• `/health` - статус API")
    st.write("• `/metabolites/search` - поиск метаболитов")
    st.write("• `/enzymes/search` - поиск ферментов")
    st.write("• `/annotate/csv` - аннотация CSV")

with col3:
    st.info("📚 **Документация:**")
    st.write("Используйте боковую панель для тестирования API")
    st.write("Все ответы в формате JSON")
    st.write("Поддерживается пагинация")

# Примеры использования
st.header("💡 Примеры использования API")

tab1, tab2, tab3 = st.tabs(["🔍 Поиск метаболитов", "🧪 Поиск ферментов", "📁 Аннотация CSV"])

with tab1:
    st.markdown("""
    **Поиск метаболитов по названию:**
    ```python
    import requests
    
    response = requests.get("https://your-app.streamlit.app/metabolites/search", 
                          params={"q": "глюкоза", "page_size": 10})
    metabolites = response.json()
    ```
    
    **Поиск по массе:**
    ```python
    response = requests.get("https://your-app.streamlit.app/metabolites/search", 
                          params={"mass": 180.063, "tol_ppm": 10})
    ```
    """)

with tab2:
    st.markdown("""
    **Поиск ферментов:**
    ```python
    response = requests.get("https://your-app.streamlit.app/enzymes/search", 
                          params={"q": "dehydrogenase", "organism_type": "plant"})
    enzymes = response.json()
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
    """)

# Информация о развертывании
st.header("🚀 Информация о развертывании")
st.markdown("""
**Этот Streamlit сервер работает как API для:**
- Поиска метаболитов по названию, формуле и массе
- Поиска ферментов по различным параметрам  
- Аннотации CSV файлов с LC-MS данными

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
st.markdown("🧬 **Protein API Server** - API сервер на базе Streamlit")

