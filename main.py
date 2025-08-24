import streamlit as st
import pandas as pd
import requests
import io
from typing import List, Dict, Any
import math
import plotly.express as px
import plotly.graph_objects as go

# -------------------------
# Вспомогательные стили/утилиты UI
# -------------------------

def _inject_base_css() -> None:
    """Добавляет базовые CSS-стили для карточек, шапки-метрик и таблиц."""
    st.markdown(
        """
        <style>
        /* Контейнер KPI карточек */
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

        /* Карточки результатов */
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
        .row-divider { height: 6px; }
        .ext-link a { text-decoration: none; font-size: 12px; }
        .ext-link a:hover { text-decoration: underline; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi(label: str, value: str, sub: str = "") -> None:
    """Рисует KPI-карточку в текущем контейнере Streamlit."""
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


def _get_totals(api_base: str) -> Dict[str, Any]:
    """Возвращает агрегированные счетчики для шапки: метаболиты, ферменты и статус API."""
    totals = {"metabolites": None, "enzymes": None, "api_status": "unknown"}

    # Статус API
    try:
        resp = requests.get(f"{api_base}/health", timeout=5)
        if resp.ok:
            data = resp.json()
            totals["api_status"] = data.get("status", "unknown")
            # Бонус: некоторые реализации возвращают metabolites_count
            if data.get("metabolites_count") is not None:
                totals["metabolites"] = int(data["metabolites_count"])
    except Exception:
        totals["api_status"] = "offline"

    # Общее число метаболитов через поиск (если не получили из /health)
    if totals["metabolites"] is None:
        try:
            resp = requests.get(f"{api_base}/metabolites/search", params={"page_size": 1}, timeout=10)
            if resp.ok:
                totals["metabolites"] = int(resp.json().get("total", 0))
        except Exception:
            totals["metabolites"] = None

    # Общее число ферментов
    try:
        resp = requests.get(f"{api_base}/enzymes/search", params={"page_size": 1}, timeout=10)
        if resp.ok:
            totals["enzymes"] = int(resp.json().get("total", 0))
    except Exception:
        totals["enzymes"] = None

    return totals


def _render_metabolite_card(m: Dict[str, Any]) -> None:
    """Карточка метаболита: название, формула, масса, класс и внешние ID."""
    name = m.get("name") or "Без названия"
    formula = m.get("formula") or "—"
    mass = m.get("exact_mass")
    mass_fmt = f"{mass:.6f} Da" if isinstance(mass, (int, float)) else "—"
    cls = m.get("class_name") or "—"

    links = []
    if m.get("hmdb_id"):
        links.append(f"<span class='ext-link'><a href='https://hmdb.ca/metabolites/{m['hmdb_id']}' target='_blank'>HMDB</a></span>")
    if m.get("kegg_id"):
        links.append(f"<span class='ext-link'><a href='https://www.kegg.jp/entry/{m['kegg_id']}' target='_blank'>KEGG</a></span>")
    if m.get("chebi_id"):
        links.append(f"<span class='ext-link'><a href='https://www.ebi.ac.uk/chebi/searchId.do?chebiId={m['chebi_id']}' target='_blank'>ChEBI</a></span>")
    if m.get("pubchem_cid"):
        links.append(f"<span class='ext-link'><a href='https://pubchem.ncbi.nlm.nih.gov/compound/{m['pubchem_cid']}' target='_blank'>PubChem</a></span>")
    links_html = " &middot; ".join(links) if links else ""

    pills = []
    if cls and cls != "—":
        pills.append(f"<span class='pill'>{cls}</span>")
    pills_html = " ".join(pills)

    st.markdown(
        f"""
        <div class="card">
          <div class="card-title">{name}</div>
          <div class="card-subtitle">Формула: <b>{formula}</b> &nbsp;|&nbsp; Масса: <b>{mass_fmt}</b></div>
          <div>{pills_html}</div>
          <div class="row-divider"></div>
          <div>{links_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_enzyme_card(e: Dict[str, Any]) -> None:
    name = e.get("name") or e.get("name_en") or "Без названия"
    ec = e.get("ec_number") or "—"
    org = e.get("organism") or "—"
    fam = e.get("family") or "—"
    props = []
    if ec != "—":
        props.append(f"EC: <b>{ec}</b>")
    if org != "—":
        props.append(f"Организм: <b>{org}</b>")
    if fam != "—":
        props.append(f"Семейство: <b>{fam}</b>")
    subtitle = " &nbsp;|&nbsp; ".join(props)
    st.markdown(
        f"""
        <div class="card">
          <div class="card-title">{name}</div>
          <div class="card-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Конфигурация API
import os
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# Настройка страницы
st.set_page_config(
    page_title="Метаболомный справочник",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Заголовок и базовые стили
_inject_base_css()
st.title("🧬 Метаболомный справочник")
st.markdown("**Учебное приложение для анализа метаболитов и аннотации данных LC-MS**")

# Отладочная информация (удалить в продакшене)
# with st.expander("🔍 DEBUG: Состояние session_state"):
#     st.write("**Метаболиты:**")
#     st.write(f"- met_page: {st.session_state.get('met_page', 'не установлен')}")
#     st.write(f"- met_search_results: {len(st.session_state.get('met_search_results', []))} результатов")
#     st.write(f"- view_mode: {st.session_state.get('view_mode', 'не установлен')}")
#     st.write(f"- search_submitted: {st.session_state.get('search_submitted', 'не установлен')}")
#     
#     st.write("**Ферменты:**")
#     st.write(f"- enz_page: {st.session_state.get('enz_page', 'не установлен')}")
#     st.write(f"- enz_view_mode: {st.session_state.get('enz_view_mode', 'не установлен')}")

# KPI панель
totals = _get_totals(API_BASE_URL)
col_k1, col_k2, col_k3 = st.columns(3)
with col_k1:
    _render_kpi("Метаболиты", f"{totals.get('metabolites') if totals.get('metabolites') is not None else '—'}", "общее количество в БД")
with col_k2:
    _render_kpi("Ферменты", f"{totals.get('enzymes') if totals.get('enzymes') is not None else '—'}", "общее количество в БД")
with col_k3:
    status = totals.get("api_status", "unknown")
    status_ru = "онлайн" if status == "healthy" else ("офлайн" if status == "offline" else status)
    _render_kpi("Статус API", status_ru, "сервис /health")

# Боковая панель - Унифицированный поиск
st.sidebar.markdown("## 🔍 **Поиск**")
st.sidebar.markdown("*Унифицированный интерфейс для поиска метаболитов и ферментов*")

# Инициализация state
if "met_page" not in st.session_state:
    st.session_state.met_page = 1
if "met_page_size" not in st.session_state:
    st.session_state.met_page_size = 50
if "met_sort_by" not in st.session_state:
    st.session_state.met_sort_by = "Релевантность"
if "search_submitted" not in st.session_state:
    st.session_state.search_submitted = False
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Карточки"
if "enz_view_mode" not in st.session_state:
    st.session_state.enz_view_mode = "Карточки"

# Переключатель типа поиска
st.sidebar.markdown("### 🎯 Выберите тип поиска")
search_type = st.sidebar.radio(
    "Тип поиска",
    options=["🧬 Метаболиты", "🧪 Ферменты"],
    horizontal=True,
    key="search_type_selector"
)

# Индикатор активного поиска
if search_type == "🧬 Метаболиты":
    st.sidebar.success("🔍 Активен поиск метаболитов")
else:
    st.sidebar.info("🔍 Активен поиск ферментов")

# Форма поиска метаболитов
if search_type == "🧬 Метаболиты":
    st.sidebar.markdown("---")
    with st.sidebar.form("metabolite_search_form"):
        st.subheader("🔍 Поиск метаболитов")
        
        mode = st.radio(
            "Режим поиска",
            options=["По названию/формуле", "По массе (m/z)"],
            horizontal=False,
        )

        search_query = ""
        mass_query = 0.0

        if mode == "По названию/формуле":
            # Инициализация preset_query
            if "preset_query" not in st.session_state:
                st.session_state.preset_query = ""
            
            search_query = st.text_input(
                "Название или формула",
                value=st.session_state.preset_query,
                placeholder="например: глюкоза, C6H12O6",
                key="met_text_query",
            )
            
            # Сброс preset после использования
            if st.session_state.preset_query:
                st.session_state.preset_query = ""
        else:
            mass_query = st.number_input(
                "Масса (m/z)", min_value=0.0, step=0.001, format="%.6f", key="met_mass_query"
            )

        col_fs1, col_fs2 = st.columns(2)
        with col_fs1:
            tolerance_ppm = st.slider("Допуск (ppm)", min_value=1, max_value=100, value=10, step=1)
        with col_fs2:
            st.session_state.met_page_size = st.selectbox(
                "Размер страницы",
                options=[25, 50, 100, 200],
                index=[25, 50, 100, 200].index(st.session_state.met_page_size)
                if st.session_state.met_page_size in [25, 50, 100, 200]
                else 1,
            )

        # Пресеты
        st.caption("💡 Быстрые пресеты:")
        presets_col1, presets_col2, presets_col3 = st.columns(3)
        with presets_col1:
            if st.form_submit_button("Глюкоза", use_container_width=True):
                st.session_state.met_page = 1
                st.session_state.preset_query = "глюкоза"
        with presets_col2:
            if st.form_submit_button("Пируват", use_container_width=True):
                st.session_state.met_page = 1
                st.session_state.preset_query = "пируват"
        with presets_col3:
            if st.form_submit_button("C6H12O6", use_container_width=True):
                st.session_state.met_page = 1
                st.session_state.preset_query = "C6H12O6"

        # Кнопка поиска
        search_submitted = st.form_submit_button("🔍 Найти метаболиты", use_container_width=True, type="primary")
        
        if search_submitted:
            st.session_state.met_page = 1
            st.session_state.search_submitted = True
            
            # Сохраняем параметры поиска для пагинации
            if mode == "По названию/формуле":
                st.session_state.last_search_query = search_query
                st.session_state.last_mass_query = None
            else:
                st.session_state.last_search_query = None
                st.session_state.last_mass_query = mass_query
            st.session_state.last_tolerance_ppm = tolerance_ppm
            
            # Выполняем поиск и сохраняем результаты
            try:
                params = {"page": 1, "page_size": st.session_state.met_page_size}
                if search_query:
                    params["q"] = search_query
                if mass_query:
                    params["mass"] = mass_query
                if tolerance_ppm:
                    params["tol_ppm"] = tolerance_ppm
                
                response = requests.get(f"{API_BASE_URL}/metabolites/search", params=params)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.met_search_results = data.get("metabolites", [])
                    st.session_state.met_total_results = data.get("total", 0)
                    st.rerun()
            except Exception:
                pass

# Форма поиска ферментов
elif search_type == "🧪 Ферменты":
    st.sidebar.markdown("---")
    with st.sidebar.form("enzyme_search_form"):
        st.subheader("🔍 Поиск ферментов")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Инициализация enz_preset_query
            if "enz_preset_query" not in st.session_state:
                st.session_state.enz_preset_query = ""
            
            enzyme_query = st.text_input(
                "Название, EC номер или организм",
                value=st.session_state.enz_preset_query,
                placeholder="Например: Ribulose, dehydrogenase, 4.1.1.39",
                help="Введите название фермента, EC номер или название организма"
            )
            
            # Сброс preset после использования
            if st.session_state.enz_preset_query:
                st.session_state.enz_preset_query = ""
            
        with col2:
            organism_type = st.selectbox(
                "🌱 Тип организма",
                ["Все", "plant", "animal", "bacteria", "fungi"],
                help="Фильтрация по типу организма"
            )
        
        # Параметры пагинации и сортировки
        if "enz_page" not in st.session_state:
            st.session_state.enz_page = 1
        if "enz_page_size" not in st.session_state:
            st.session_state.enz_page_size = 50
        if "enz_sort_by" not in st.session_state:
            st.session_state.enz_sort_by = "Релевантность"

        colp1, colp2 = st.columns(2)
        with colp1:
            st.session_state.enz_page_size = st.selectbox(
                "Размер страницы",
                options=[25, 50, 100, 200],
                index=[25, 50, 100, 200].index(st.session_state.enz_page_size)
                if st.session_state.enz_page_size in [25, 50, 100, 200]
                else 1,
            )
        with colp2:
            st.session_state.enz_sort_by = st.selectbox(
                "Сортировать по",
                options=["Релевантность", "Название", "EC", "Организм", "Семейство"],
            )

        # Пресеты
        st.caption("💡 Быстрые пресеты:")
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            if st.form_submit_button("Ribulose", use_container_width=True):
                st.session_state.enz_page = 1
                st.session_state.enz_preset_query = "Ribulose"
        with pcol2:
            if st.form_submit_button("dehydrogenase", use_container_width=True):
                st.session_state.enz_page = 1
                st.session_state.enz_preset_query = "dehydrogenase"
        with pcol3:
            if st.form_submit_button("4.1.1.39", use_container_width=True):
                st.session_state.enz_page = 1
                st.session_state.enz_preset_query = "4.1.1.39"

        submitted = st.form_submit_button("🔍 Найти ферменты", use_container_width=True, type="primary")
        
        if submitted:
            st.session_state.enz_page = 1
        
        if submitted:
            if enzyme_query or organism_type != "Все":
                try:
                    # Параметры запроса
                    params = {"page_size": st.session_state.enz_page_size, "page": st.session_state.enz_page}
                    if enzyme_query:
                        params["q"] = enzyme_query
                    if organism_type != "Все":
                        params["organism_type"] = organism_type
                    
                    # Запрос к API
                    response = requests.get(f"{API_BASE_URL}/enzymes/search", params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        enzymes = data.get("enzymes", [])
                        total = data.get("total", 0)
                        total_pages = max(1, math.ceil(total / st.session_state.enz_page_size))
                        
                        # Сохраняем результаты для использования вне формы
                        st.session_state.enz_search_results = enzymes
                        st.session_state.enz_total_results = total
                        st.session_state.enz_total_pages = total_pages
                        st.session_state.enz_last_query = enzyme_query
                        st.session_state.enz_last_organism_type = organism_type
                        st.session_state.enz_search_submitted = True
                        
                        if enzymes:
                            st.success(f"✅ Найдено {total} ферментов")
                        else:
                            st.warning("🔍 Ферменты не найдены. Попробуйте изменить параметры поиска.")
                    else:
                        st.error(f"❌ Ошибка поиска: {response.status_code}")
                        
                except requests.exceptions.RequestException:
                    st.error("❌ Не удается подключиться к API серверу")
                except Exception as e:
                    st.error(f"❌ Ошибка: {str(e)}")
            else:
                st.warning("🔍 Введите поисковый запрос или выберите тип организма")
    
    # Подсказка внизу боковой панели
    st.sidebar.markdown("---")
    st.sidebar.caption("💡 **Совет:** Результаты поиска отображаются в основном контенте")

# Основной контент
# Проверяем, есть ли сохраненные результаты поиска метаболитов
if st.session_state.get("search_submitted", False) and st.session_state.get("met_search_results"):
    st.header("📊 Результаты поиска метаболитов")
    
    # Используем сохраненные результаты поиска
    metabolites = st.session_state.get("met_search_results", [])
    total = st.session_state.get("met_total_results", 0)
    total_pages = max(1, math.ceil(total / st.session_state.met_page_size))
    
    if metabolites:
        st.success(f"✅ Найдено {len(metabolites)} метаболитов")

        # Сортировка и вид (вынесено наверх для стабильности)
        col_v1, col_v2 = st.columns([1, 1])
        with col_v1:
            st.session_state.met_sort_by = st.selectbox(
                "Сортировать по",
                options=["Релевантность", "Название", "Масса", "Класс"],
                index=["Релевантность", "Название", "Масса", "Класс"].index(
                    st.session_state.met_sort_by
                )
                if st.session_state.met_sort_by in ["Релевантность", "Название", "Масса", "Класс"]
                else 0,
                key="met_sort_select"
            )
        with col_v2:
            view_choice = st.radio(
                "Вид", 
                options=["Карточки", "Таблица"], 
                horizontal=True, 
                index=["Карточки", "Таблица"].index(st.session_state.view_mode),
                key="met_view_radio"
            )
            if view_choice != st.session_state.view_mode:
                st.session_state.view_mode = view_choice

        # Применяем сортировку
        if st.session_state.met_sort_by != "Релевантность":
            key_map = {
                "Название": lambda m: (m.get("name") or "").lower(),
                "Масса": lambda m: m.get("exact_mass") or 0,
                "Класс": lambda m: (m.get("class_name") or "").lower(),
            }
            metabolites = sorted(metabolites, key=key_map[st.session_state.met_sort_by])
            # Обновляем сохраненные результаты
            st.session_state.met_search_results = metabolites

        # Табличное представление
        df_data = []
        for met in metabolites:
            df_data.append({
                "Название": met.get("name", ""),
                "Формула": met.get("formula", ""),
                "Масса": f"{met['exact_mass']:.6f}" if isinstance(met.get('exact_mass'), (int, float)) else "",
                "Класс": met.get("class_name", ""),
                "HMDB ID": met.get("hmdb_id", ""),
                "KEGG ID": met.get("kegg_id", ""),
                "ChEBI ID": met.get("chebi_id", ""),
                "PubChem CID": met.get("pubchem_cid", "")
            })
        df = pd.DataFrame(df_data)

        if st.session_state.view_mode == "Таблица":
            st.dataframe(df, use_container_width=True)
        else:
            # Карточки, 3 колонки
            cols = st.columns(3)
            for idx, met in enumerate(metabolites):
                with cols[idx % 3]:
                    _render_metabolite_card(met)

        # Гистограмма по массе (если есть данные)
        if len(df) and (df["Масса"] != "").any():
            try:
                df_mass = df[df["Масса"] != ""].copy()
                df_mass["Масса"] = df_mass["Масса"].astype(float)
                st.subheader("📈 Распределение масс (m/z) в результатах")
                fig = px.histogram(df_mass, x="Масса", nbins=30, height=280)
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

# Проверяем, есть ли сохраненные результаты поиска ферментов
if st.session_state.get("enz_search_submitted", False) and st.session_state.get("enz_search_results"):
    st.header("📊 Результаты поиска ферментов")
    
    # Используем сохраненные результаты поиска
    enzymes = st.session_state.get("enz_search_results", [])
    total = st.session_state.get("enz_total_results", 0)
    
    if enzymes:
        st.success(f"✅ Найдено {len(enzymes)} ферментов")
        
        # Переключение вида и сортировка (вынесено наверх для стабильности)
        col_v1, col_v2 = st.columns([1, 1])
        with col_v1:
            st.session_state.enz_sort_by = st.selectbox(
                "Сортировать по",
                options=["Релевантность", "Название", "EC", "Организм", "Семейство"],
                index=["Релевантность", "Название", "EC", "Организм", "Семейство"].index(
                    st.session_state.enz_sort_by
                )
                if st.session_state.enz_sort_by in ["Релевантность", "Название", "EC", "Организм", "Семейство"]
                else 0,
                key="enz_sort_select"
            )
        with col_v2:
            enz_view_choice = st.radio(
                "Вид", 
                options=["Карточки", "Таблица"], 
                horizontal=True, 
                index=["Карточки", "Таблица"].index(st.session_state.enz_view_mode),
                key="enz_view_radio"
            )
            if enz_view_choice != st.session_state.enz_view_mode:
                st.session_state.enz_view_mode = enz_view_choice

        # Таблица данных для отображения
        df_data = []
        for enzyme in enzymes:
            df_data.append({
                "ID": enzyme.get("id"),
                "Название": enzyme.get("name", ""),
                "EC номер": enzyme.get("ec_number", ""),
                "Организм": enzyme.get("organism", ""),
                "Тип": enzyme.get("organism_type", ""),
                "Семейство": enzyme.get("family", ""),
                "Мол. масса (kDa)": enzyme.get("molecular_weight"),
                "Опт. pH": enzyme.get("optimal_ph"),
                "Опт. T°C": enzyme.get("optimal_temperature"),
                "Локализация": enzyme.get("subcellular_location", "")
            })
        df = pd.DataFrame(df_data)

        # Применяем сортировку
        if st.session_state.enz_sort_by != "Релевантность" and len(df):
            sort_map = {
                "Название": "Название",
                "EC": "EC номер",
                "Организм": "Организм",
                "Семейство": "Семейство",
            }
            if st.session_state.enz_sort_by in sort_map:
                df = df.sort_values(by=sort_map[st.session_state.enz_sort_by], kind="mergesort")
                # также сортируем карточки
                key_funcs = {
                    "Название": lambda e: (e.get("name") or "").lower(),
                    "EC": lambda e: (e.get("ec_number") or ""),
                    "Организм": lambda e: (e.get("organism") or "").lower(),
                    "Семейство": lambda e: (e.get("family") or "").lower(),
                }
                enzymes = sorted(enzymes, key=key_funcs[st.session_state.enz_sort_by])
                # Обновляем сохраненные результаты
                st.session_state.enz_search_results = enzymes

        # Отображение в выбранном виде
        if st.session_state.enz_view_mode == "Таблица":
            st.dataframe(df, use_container_width=True)
        else:
            # Карточки, 3 колонки
            cols = st.columns(3)
            for idx, e in enumerate(enzymes):
                with cols[idx % 3]:
                    _render_enzyme_card(e)

        # Детальная информация (селектор)
        with st.expander("📋 Детальная информация по ферменту"):
            selected_enzyme_id = st.selectbox(
                "Выберите фермент:",
                options=[e["id"] for e in enzymes],
                format_func=lambda x: f"{x}: {next(e['name'] for e in enzymes if e['id'] == x)}"
            )

            if selected_enzyme_id:
                selected_enzyme = next(e for e in enzymes if e["id"] == selected_enzyme_id)
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Основная информация:**")
                    st.write(f"**Название:** {selected_enzyme.get('name', 'Не указано')}")
                    st.write(f"**Белок:** {selected_enzyme.get('protein_name', 'Не указано')}")
                    st.write(f"**Ген:** {selected_enzyme.get('gene_name', 'Не указано')}")
                    st.write(f"**EC номер:** {selected_enzyme.get('ec_number', 'Не указано')}")
                    st.write(f"**Семейство:** {selected_enzyme.get('family', 'Не указано')}")
                    st.write(f"**UniProt ID:** {selected_enzyme.get('uniprot_id', 'Не указано')}")
                with col2:
                    st.markdown("**Биохимические свойства:**")
                    if selected_enzyme.get('molecular_weight'):
                        st.write(f"**Мол. масса:** {selected_enzyme['molecular_weight']:.1f} kDa")
                    if selected_enzyme.get('optimal_ph'):
                        st.write(f"**Оптимальный pH:** {selected_enzyme['optimal_ph']}")
                    if selected_enzyme.get('optimal_temperature'):
                        st.write(f"**Оптимальная T:** {selected_enzyme['optimal_temperature']}°C")
                    st.write(f"**Организм:** {selected_enzyme.get('organism', 'Не указано')}")
                    st.write(f"**Локализация:** {selected_enzyme.get('subcellular_location', 'Не указано')}")
                if selected_enzyme.get('description'):
                    st.markdown("**Описание функции:**")
                    st.write(selected_enzyme['description'])
                if selected_enzyme.get('tissue_specificity'):
                    st.markdown("**Тканевая специфичность:**")
                    st.write(selected_enzyme['tissue_specificity'])

# Пагинация для метаболитов
if st.session_state.get("search_submitted", False) and st.session_state.get("met_total_results", 0):
    total = st.session_state.get("met_total_results", 0)
    total_pages = max(1, math.ceil(total / st.session_state.met_page_size))
    
    if total_pages > 1:
        st.subheader("📄 Пагинация метаболитов")
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("⬅️ Предыдущая", disabled=st.session_state.met_page <= 1, key="met_prev"):
                st.session_state.met_page = max(1, st.session_state.met_page - 1)
                # Обновляем результаты для новой страницы
                try:
                    params = {"page": st.session_state.met_page, "page_size": st.session_state.met_page_size}
                    if st.session_state.get("last_search_query"):
                        params["q"] = st.session_state.last_search_query
                    if st.session_state.get("last_mass_query"):
                        params["mass"] = st.session_state.last_mass_query
                    if st.session_state.get("last_tolerance_ppm"):
                        params["tol_ppm"] = st.session_state.last_tolerance_ppm
                    
                    response = requests.get(f"{API_BASE_URL}/metabolites/search", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.met_search_results = data.get("metabolites", [])
                        st.rerun()
                except Exception:
                    pass
        with pc2:
            st.markdown(f"Страница {st.session_state.met_page} из {total_pages}")
        with pc3:
            if st.button("Следующая ➡️", disabled=st.session_state.met_page >= total_pages, key="met_next"):
                st.session_state.met_page = min(total_pages, st.session_state.met_page + 1)
                # Обновляем результаты для новой страницы
                try:
                    params = {"page": st.session_state.met_page, "page_size": st.session_state.met_page_size}
                    if st.session_state.get("last_search_query"):
                        params["q"] = st.session_state.last_search_query
                    if st.session_state.get("last_mass_query"):
                        params["mass"] = st.session_state.last_mass_query
                    if st.session_state.get("last_tolerance_ppm"):
                        params["tol_ppm"] = st.session_state.last_tolerance_ppm
                    
                    response = requests.get(f"{API_BASE_URL}/metabolites/search", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.met_search_results = data.get("metabolites", [])
                        st.rerun()
                except Exception:
                    pass

# Пагинация для ферментов
if st.session_state.get("enz_search_submitted", False) and st.session_state.get("enz_total_results", 0):
    total = st.session_state.get("enz_total_results", 0)
    total_pages = max(1, math.ceil(total / st.session_state.enz_page_size))
    
    if total_pages > 1:
        st.subheader("📄 Пагинация ферментов")
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        
        with pc1:
            if st.button("⬅️ Предыдущая", key="enz_prev", disabled=st.session_state.enz_page <= 1):
                st.session_state.enz_page = max(1, st.session_state.enz_page - 1)
                # Обновляем результаты для новой страницы
                try:
                    params = {"page": st.session_state.enz_page, "page_size": st.session_state.enz_page_size}
                    if st.session_state.get("enz_last_query"):
                        params["q"] = st.session_state.enz_last_query
                    if st.session_state.get("enz_last_organism_type") != "Все":
                        params["organism_type"] = st.session_state.enz_last_organism_type
                    
                    response = requests.get(f"{API_BASE_URL}/enzymes/search", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.enz_search_results = data.get("enzymes", [])
                        st.rerun()
                except Exception:
                    pass
                    
        with pc2:
            st.markdown(f"Страница {st.session_state.enz_page} из {total_pages}")
            
        with pc3:
            if st.button("Следующая ➡️", key="enz_next", disabled=st.session_state.enz_page >= total_pages):
                st.session_state.enz_page = min(total_pages, st.session_state.enz_page + 1)
                # Обновляем результаты для новой страницы
                try:
                    params = {"page": st.session_state.enz_page, "page_size": st.session_state.enz_page_size}
                    if st.session_state.get("enz_last_query"):
                        params["q"] = st.session_state.enz_last_query
                    if st.session_state.get("enz_last_organism_type") != "Все":
                        params["organism_type"] = st.session_state.enz_last_organism_type
                    
                    response = requests.get(f"{API_BASE_URL}/enzymes/search", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.enz_search_results = data.get("enzymes", [])
                        st.rerun()
                except Exception:
                    pass

# Вкладки для разных функций
tab1, tab2, tab3, tab4 = st.tabs(["🔍 Поиск метаболитов", "🧪 Поиск ферментов", "📁 Аннотация CSV", "📚 Справка"])

with tab1:
    st.header("🔍 Поиск метаболитов")
    st.markdown("""
    **Используйте боковую панель для поиска метаболитов!**
    
    Поиск доступен по:
    - **Названию** (например: глюкоза, пируват)
    - **Химической формуле** (например: C6H12O6)
    - **Массе (m/z)** с указанием допуска в ppm
    """)
    
    # Примеры поиска
    st.subheader("💡 Примеры поиска")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**По названию:**")
        st.code("глюкоза")
        st.code("пируват")
        st.code("аланин")
    
    with col2:
        st.markdown("**По массе:**")
        st.code("180.063 ±10 ppm")
        st.code("88.016 ±5 ppm")
        st.code("507.182 ±20 ppm")

with tab2:
    st.header("🧪 Поиск ферментов")
    st.markdown("""
    **Используйте боковую панель для поиска ферментов!** 
    
    Поиск доступен по:
    - **Названию** (например: Ribulose, dehydrogenase)
    - **EC номеру** (например: 4.1.1.39, 1.1.1)
    - **Организму** (например: Arabidopsis, Cucumis)
    - **Типу организма** (plant, animal, bacteria, fungi)
    """)
    
    # Примеры поиска ферментов
    st.subheader("💡 Примеры поиска ферментов")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**По названию:**")
        st.code("RuBisCO")
        st.code("Глутамин-синтетаза")
        st.code("Нитрат-редуктаза")
        
        st.markdown("**По семейству:**")
        st.code("Оксидоредуктазы")
        st.code("Трансферазы")
        st.code("Гидролазы")
    
    with col2:
        st.markdown("**По EC номеру:**")
        st.code("4.1.1.39")
        st.code("6.3.1.2")
        st.code("1.7.1.1")
        
        st.markdown("**По организму:**")
        st.code("Arabidopsis")
        st.code("Растения")
        st.code("plant")

with tab3:
    st.header("📁 Аннотация CSV файлов")
    st.markdown("Загрузите CSV файл с пиками LC-MS для автоматической аннотации метаболитами")
    
    # Загрузка файла
    uploaded_file = st.file_uploader(
        "Выберите CSV файл",
        type=['csv'],
        help="Файл должен содержать столбец с массами (m/z)"
    )
    
    if uploaded_file is not None:
        try:
            # Читаем CSV
            df = pd.read_csv(uploaded_file)
            st.success(f"✅ Файл загружен: {len(df)} строк")
            
            # Показываем первые строки
            st.subheader("📊 Предварительный просмотр")
            st.dataframe(df.head(), use_container_width=True)
            
            # Выбор столбца с массами
            if len(df.columns) > 0:
                mass_column = st.selectbox(
                    "Выберите столбец с массами (m/z):",
                    df.columns,
                    index=0
                )
                
                # Параметры аннотации
                col1, col2 = st.columns(2)
                with col1:
                    annotation_tolerance = st.slider(
                        "Допуск аннотации (ppm):",
                        min_value=1,
                        max_value=100,
                        value=10,
                        step=1
                    )
                
                with col2:
                    max_candidates = st.slider(
                        "Максимум кандидатов:",
                        min_value=1,
                        max_value=20,
                        value=5,
                        step=1
                    )
                
                # Кнопка аннотации
                if st.button("🔬 Начать аннотацию", type="primary"):
                    with st.spinner("Выполняется аннотация..."):
                        try:
                            # Подготавливаем данные для API
                            mz_values = df[mass_column].astype(float).tolist()
                            
                            # Вызываем API для аннотации
                            response = requests.post(
                                f"{API_BASE_URL}/annotate/csv",
                                files={"file": uploaded_file.getvalue()},
                                data={
                                    "mz_column": mass_column,
                                    "tol_ppm": annotation_tolerance
                                }
                            )
                            
                            if response.status_code == 200:
                                annotation_data = response.json()
                                st.success("✅ Аннотация завершена!")
                                
                                # Показываем результаты
                                st.subheader("📋 Результаты аннотации")
                                
                                results_data = []
                                for item in annotation_data.get("items", []):
                                    mz = item["mz"]
                                    candidates = item.get("candidates", [])
                                    best_match = item.get("best_match")
                                    
                                    results_data.append({
                                        "m/z": mz,
                                        "Кандидаты": ", ".join(candidates[:3]) if candidates else "Не найдено",
                                        "Лучший кандидат": best_match["name"] if best_match else "Не выбран",
                                        "Формула": best_match["formula"] if best_match else "",
                                        "Класс": best_match.get("class_name", "") if best_match else ""
                                    })
                                
                                results_df = pd.DataFrame(results_data)
                                st.dataframe(results_df, use_container_width=True)
                                
                                # Экспорт результатов
                                st.subheader("💾 Экспорт результатов")
                                
                                # CSV экспорт
                                csv_buffer = io.StringIO()
                                results_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                                csv_data = csv_buffer.getvalue()
                                
                                st.download_button(
                                    label="📥 Скачать CSV",
                                    data=csv_data,
                                    file_name="annotation_results.csv",
                                    mime="text/csv"
                                )
                                
                                # Excel экспорт
                                excel_buffer = io.BytesIO()
                                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                                    results_df.to_excel(writer, sheet_name='Аннотация', index=False)
                                excel_data = excel_buffer.getvalue()
                                
                                st.download_button(
                                    label="📥 Скачать Excel",
                                    data=excel_data,
                                    file_name="annotation_results.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                                
                            else:
                                st.error(f"❌ Ошибка API: {response.status_code}")
                                
                        except requests.exceptions.ConnectionError:
                            st.error("❌ Не удается подключиться к API серверу")
                        except Exception as e:
                            st.error(f"❌ Ошибка аннотации: {str(e)}")
            else:
                st.warning("⚠️ CSV файл не содержит столбцов")
                
        except Exception as e:
            st.error(f"❌ Ошибка чтения файла: {str(e)}")

with tab4:
    st.header("📚 Справка по использованию")
    
    st.subheader("🎯 Назначение приложения")
    st.markdown("""
    **Метаболомный справочник** - это учебное приложение для:
    - Поиска метаболитов по массе, названию и химической формуле
    - Поиска растительных ферментов по различным параметрам
    - Аннотации пиков LC-MS данных
    - Изучения биохимических путей и ферментов
    - Создания справочных таблиц для лабораторных работ
    """)
    
    st.subheader("🔍 Как искать метаболиты")
    st.markdown("""
    1. **По названию**: Введите название метаболита (например: глюкоза, пируват)
    2. **По формуле**: Введите химическую формулу (например: C6H12O6)
    3. **По массе**: Укажите массу (m/z) и допустимое отклонение в ppm
    """)
    
    st.subheader("🧪 Как искать ферменты")
    st.markdown("""
    1. **По названию**: Введите полное или частичное название (например: Ribulose, dehydrogenase)
    2. **По EC номеру**: Введите номер классификации (например: 4.1.1.39, 1.1.1)
    3. **По организму**: Введите название организма (например: Arabidopsis, Cucumis)
    4. **По типу**: Выберите тип организма из списка (plant, animal, bacteria, fungi)
    
    **Примеры поисковых запросов:**
    - "Ribulose" → найдет RuBisCO и другие ферменты с рибулозой
    - "4.1.1.39" → найдет точно RuBisCO по EC номеру
    - "dehydrogenase" → найдет все дегидрогеназы
    """)
    
    st.subheader("📁 Как аннотировать CSV файлы")
    st.markdown("""
    1. Подготовьте CSV файл со столбцом, содержащим массы (m/z)
    2. Загрузите файл в разделе "Аннотация CSV"
    3. Выберите столбец с массами
    4. Установите параметры аннотации (допуск, количество кандидатов)
    5. Запустите аннотацию
    6. Экспортируйте результаты в CSV или Excel
    """)
    
    st.subheader("📊 Формат CSV файла")
    st.markdown("""
    Пример структуры CSV файла:
    ```csv
    mz,intensity,rt
    180.063,120000,85.2
    255.232,55000,76.1
    507.182,89000,92.3
    ```
    """)
    
    st.subheader("🔗 Источники данных")
    st.markdown("""
    Приложение использует данные из открытых баз:
    - **HMDB** (Human Metabolome Database)
    - **KEGG** (Kyoto Encyclopedia of Genes and Genomes)
    - **ChEBI** (Chemical Entities of Biological Interest)
    - **PubChem** (Chemical Database)
    """)
    
    st.subheader("📚 Учебные сценарии")
    st.markdown("""
    - **Лабораторная работа**: "Аннотируйте 20 пиков LC-MS, выделите три ключевых метаболита"
    - **Задание**: "Найдите метаболиты для массы 180.063 ±10 ppm и составьте таблицу ссылок"
    - **Демонстрация**: "Свяжите найденные метаболиты с путями гликолиза и цикла Кребса"
    """)

# Футер
st.markdown("---")
st.markdown("🧬 **Метаболомный справочник** - Учебное приложение для курсов по биохимии и химии")

