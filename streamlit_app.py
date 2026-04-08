# main file (frontend)
import json
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from src.external_api import map_widget_iframe_html
except ImportError:
    map_widget_iframe_html = None


DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_MAP_ZOOM = 15
DEFAULT_STATUS_ORDER = ["free", "busy",
                        "probably_free", "unavailable", "unknown"]
HISTORY_DEFAULT_LIMIT = 20


def request_json(method: str, url: str, **kwargs) -> Optional[Any]:
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
        response.raise_for_status()
        if response.headers.get(
                "content-type", "").startswith("application/json"):
            return response.json()
        return response.text
    except requests.RequestException as error:
        st.error(f"Ошибка запроса к API: {error}")
        return None


def fetch_machines(DEFAULT_API_BASE_URL: str) -> List[Dict[str, Any]]:
    data = request_json(
        "GET",
        f"{DEFAULT_API_BASE_URL.rstrip('/')}/machines",
        params={"_": int(time.time())},
        headers={"Cache-Control": "no-cache"},
    )
    if isinstance(data, list):
        return data
    return []


def fetch_history(
    DEFAULT_API_BASE_URL: str,
        machine_id: int, limit: int = HISTORY_DEFAULT_LIMIT
) -> List[Dict[str, Any]]:
    data = request_json(
        "GET",
        f"{DEFAULT_API_BASE_URL.rstrip('/')}/machines/{machine_id}/history",
        params={"limit": limit, "_": int(time.time())},
        headers={"Cache-Control": "no-cache"},
    )
    if isinstance(data, list):
        return data
    return []


def submit_report(
    DEFAULT_API_BASE_URL: str, report_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    return request_json(
        "POST",
        f"{DEFAULT_API_BASE_URL.rstrip('/')}/report",
        headers={"Content-Type": "application/json",
                 "Cache-Control": "no-cache"},
        data=json.dumps(report_data),
    )


def normalize_status(status_value: Any) -> str:
    if status_value is None:
        return "unknown"
    text = str(status_value).lower()
    if any(
        keyword in text
        for keyword in [
            "unavailable",
            "broken",
            "error",
            "fault",
            "сломана",
            "неисправ",
        ]
    ):
        return "unavailable"
    # important: check unavailable first,
    # because "unavailable" contains "available"
    if any(
        keyword in text
        for keyword in ["busy", "process", "running", "занят", "в процессе"]
    ):
        return "busy"
    if any(keyword in text for keyword in [
            "probably_free", "скорее свободна"]):
        return "probably_free"
    if any(keyword in text for keyword in [
            "free", "available", "свободна", "idle"]):
        return "free"
    return "unknown"


def status_to_label(status_value: Any) -> str:
    normalized = normalize_status(status_value)
    if normalized == "free":
        return "Свободна"
    if normalized == "busy":
        return "В процессе"
    if normalized == "probably_free":
        return "Скорее свободна"
    if normalized == "unavailable":
        return "Сломана"
    return str(status_value or "Неизвестно")


def status_badge_html(status_value: Any) -> str:
    status = normalize_status(status_value)
    colors = {
        "free": "#22c55e",  # green
        "busy": "#ef4444",  # red
        "probably_free": "#facc15",  # yellow
        "unavailable": "#9ca3af",  # grey
        "unknown": "#9ca3af",
    }
    color = colors.get(status, "#9ca3af")
    return (
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:999px;background:{color};margin-right:8px;"></span>'
    )


def status_sort_key(machine: Dict[str, Any]) -> int:
    status = get_display_status(machine)
    try:
        return DEFAULT_STATUS_ORDER.index(status)
    except ValueError:
        return len(DEFAULT_STATUS_ORDER) - 1


def extract_floor(machine: Dict[str, Any]) -> Optional[int]:
    for key in ["floor", "level", "этаж", "floor_number", "этаж_номер"]:
        if key in machine:
            try:
                return int(machine[key])
            except (TypeError, ValueError):
                continue
    return None


def extract_building(machine: Dict[str, Any]) -> Optional[str]:
    for key in ["building", "corp", "корпус", "block", "house"]:
        if key in machine and machine[key] is not None:
            return str(machine[key]).strip()
    return None


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        # backend returns iso strings
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_remaining_minutes(machine: Dict[str, Any]) -> Optional[int]:
    now = datetime.now(timezone.utc)

    estimated_free_at = _parse_iso_datetime(machine.get("estimated_free_at"))
    if estimated_free_at is not None:
        remaining = int((estimated_free_at - now).total_seconds() // 60)
        return max(0, remaining)

    last_report_at = _parse_iso_datetime(machine.get("last_report_at"))
    time_remaining = machine.get("time_remaining")
    if last_report_at is None or time_remaining is None:
        return None
    try:
        minutes = int(time_remaining)
    except (TypeError, ValueError):
        return None

    ends_at = last_report_at + timedelta(minutes=minutes)
    remaining = int((ends_at - now).total_seconds() // 60)
    return max(0, remaining)


def get_display_status(machine: Dict[str, Any]) -> str:
    base = normalize_status(
        machine.get("inferred_status") or machine.get("reported_status")
    )
    if base == "unavailable":
        return "unavailable"
    remaining = compute_remaining_minutes(machine)
    if remaining is not None and remaining > 0:
        return "busy"
    return base


def format_machine_name(machine: Dict[str, Any]) -> str:
    machine_id = machine.get("id") or machine.get(
        "machine_id") or machine.get("name")
    if machine_id is None:
        return "Без номера"
    return str(machine_id)


def filter_and_sort_machines(
    machines: List[Dict[str, Any]],
    selected_building: Optional[str],
    selected_floor: int,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for machine in machines:
        floor = extract_floor(machine)
        building = extract_building(machine)
        if selected_building and building and selected_building != building:
            continue
        if floor == selected_floor:
            filtered.append(machine)
    return sorted(
        filtered,
        key=lambda machine: (
            status_sort_key(machine),
            extract_floor(machine) or 0,
            format_machine_name(machine),
        ),
    )


def render_report_panel(
    DEFAULT_API_BASE_URL: str, selected_machine_id: Optional[str]
) -> None:
    st.subheader("Создать репорт")
    machines = fetch_machines(DEFAULT_API_BASE_URL)
    machine_ids = [m.get("id") for m in machines if isinstance(
        m.get("id"), int)]
    machine_ids.sort()

    if not machine_ids:
        st.warning("Не удалось загрузить список машин")
        return

    def _label(mid: int) -> str:
        for m in machines:
            if m.get("id") == mid:
                return (
                    f"#{mid} • {m.get('name', '—')} • {m.get('type', '—')} • "
                    f"корпус {m.get('building', '—')} • этаж {
                        m.get('floor', '—')}"
                )
        return f"#{mid}"

    default_id = (
        int(selected_machine_id)
        if selected_machine_id and selected_machine_id.isdigit()
        else machine_ids[0]
    )
    machine_id = st.selectbox(
        "Машина",
        machine_ids,
        index=machine_ids.index(
            default_id) if default_id in machine_ids else 0,
        format_func=_label,
    )

    status = st.radio(
        "Статус машины",
        ["busy", "free", "unavailable"],
        format_func=lambda value: {
            "busy": "В процессе",
            "free": "Свободна",
            "unavailable": "Сломана",
        }[value],
        horizontal=True,
    )

    time_remaining = None
    if status == "busy":
        time_remaining = st.number_input(
            "Время до конца (мин)",
            min_value=0,
            value=10,
            step=5,
        )
    else:
        st.info("Время до конца используется только для статуса 'В процессе'.")

    reporter_name = st.text_input("Ваше имя (необязательно)", value="")

    if st.button("Отправить отчет"):
        payload = {
            "machine_id": int(machine_id),
            "status": status,
            "time_remaining": time_remaining if status == "busy" else None,
            "reporter_name": reporter_name.strip() or None,
        }
        result = submit_report(DEFAULT_API_BASE_URL, payload)
        if result is not None:
            st.success("Отчет отправлен успешно")
            st.json(result)
            st.session_state.selected_report_machine = None
            st.rerun()


def render_machine_list(
    DEFAULT_API_BASE_URL: str,
    building: Optional[str],
    floor: int,
    *,
    show_all: bool,
    cards_per_row: int,
) -> Optional[str]:
    machines = fetch_machines(DEFAULT_API_BASE_URL)
    if not machines:
        st.info("Нет данных о машинах. "
                "Проверьте URL бэкенда и доступность сервиса.")
        return None

    if show_all:
        st.subheader("Все машины")
        filtered_machines = sorted(machines, key=status_sort_key)
    else:
        st.subheader(f"Корпус {building or '—'} • этаж {floor}")
        filtered_machines = filter_and_sort_machines(machines, building, floor)
    if not filtered_machines:
        st.write("Нет машин.")
        return None

    rows = [
        filtered_machines[i: i + cards_per_row]
        for i in range(0, len(filtered_machines), cards_per_row)
    ]

    for row_machines in rows:
        cols = st.columns(cards_per_row)
        for col, machine in zip(cols, row_machines):
            mid = int(machine.get("id"))
            machine_floor = extract_floor(machine)
            machine_building = extract_building(machine)
            normalized_status = get_display_status(machine)
            status_label = status_to_label(normalized_status)
            remaining_minutes = compute_remaining_minutes(machine)
            time_remaining = (
                str(remaining_minutes)
                if normalized_status == "busy"
                and remaining_minutes is not None
                else None
            )

            with col:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div style="line-height:1.15">
                            <div style="font-weight:700;margin:0 0 6px 0;">#{
                                mid} • {machine.get('name', '—')}</div>
                            <div style="margin:0 0 4px 0;">тип: <b>{
                                machine.get('type', '—')}</b></div>
                            <div style="margin:0 0 4px 0;">корпус: <b>{
                                machine_building or '—'}</b> • этаж: <b>{
                                    machine_floor if machine_floor
                                    is not None else '—'}</b></div>
                            <div style="margin:0 0 4px 0;">статус: {
                                status_badge_html(normalized_status)}<b>{status_label}</b></div>
                            <div style="margin:0;">осталось: <b>{
                                time_remaining or '—'}</b></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        "<div style='height:1px'></div>",
                        unsafe_allow_html=True
                    )

                    if normalized_status != "busy":
                        if st.button("Создать репорт", key=f"report_{mid}"):
                            st.session_state.selected_report_machine = str(mid)
                    else:
                        st.caption("в процессе")

                    st.markdown(
                        "<div style='height:2px'></div>",
                        unsafe_allow_html=True
                    )

                    if st.button("История", key=f"history_{mid}",
                                 type="tertiary"):
                        st.session_state.history_machine_id = mid

    if "selected_report_machine" not in st.session_state:
        st.session_state.selected_report_machine = None
    if "history_machine_id" not in st.session_state:
        st.session_state.history_machine_id = None

    if st.session_state.selected_report_machine:
        st.markdown("---")
        st.info(
            f"Создать репорт для машины: {
                st.session_state.selected_report_machine}"
        )
        render_report_panel(
            DEFAULT_API_BASE_URL, st.session_state.selected_report_machine
        )

    if st.session_state.history_machine_id:
        render_history_panel(DEFAULT_API_BASE_URL,
                             st.session_state.history_machine_id)
        st.session_state.history_machine_id = None

    return st.session_state.selected_report_machine


@st.dialog("История репортов")
def render_history_panel(DEFAULT_API_BASE_URL: str, machine_id: int) -> None:
    # parsed json in a modal window
    st.markdown(f"**Машина #{machine_id}**")
    history = fetch_history(
        DEFAULT_API_BASE_URL, machine_id, limit=HISTORY_DEFAULT_LIMIT
    )
    if not history:
        st.info("История пуста или машина не найдена.")
        return
    st.json(history)
    st.dataframe(history, use_container_width=True)


def render_yandex_map(address: str, width: int,
                      height: int, zoom: int) -> None:
    if map_widget_iframe_html is None:
        st.error(
            "Не удалось загрузить карту. Убедитесь, что модуль "
            "`src.external_api` и его зависимости доступны."
        )
        return

    try:
        map_html = map_widget_iframe_html(
            address, width=width, height=height, zoom=zoom
        )
        components.html(map_html, height=height + 20, scrolling=False)
    except Exception as error:
        st.error(f"Ошибка создания карты: {error}")


def main() -> None:
    st.set_page_config(page_title="SQRS Project", layout="wide")
    st.title("Laundry Monitor")
    st.markdown(
        "Введите корпус и этаж на боковой панели, "
        "чтобы увидеть список машин и создать отчет."
    )

    if "selected_report_machine" not in st.session_state:
        st.session_state.selected_report_machine = None
    if "history_machine_id" not in st.session_state:
        st.session_state.history_machine_id = None

    st.markdown(
        """
<style>
button[kind="tertiary"] {
  padding: 0 !important;
  height: auto !important;
  min-height: 0 !important;
  text-decoration: underline !important;
}
</style>
""",
        unsafe_allow_html=True,
    )

    # persist last opened sidebar values
    # in the url (survives a full page refresh)
    qp = st.query_params
    if "view" not in st.session_state:
        # first visit should always land on "home"
        st.session_state.view = qp.get("view", "home") or "home"
    if "building" not in st.session_state:
        st.session_state.building = qp.get("building", "1")
    if "floor" not in st.session_state:
        try:
            st.session_state.floor = int(qp.get("floor", 1))
        except (TypeError, ValueError):
            st.session_state.floor = 1
    if "map_address" not in st.session_state:
        st.session_state.map_address = qp.get(
            "map_address", "Иннополис, Россия")

    def _sync_query_params() -> None:
        st.query_params.update(
            {
                "view": st.session_state.view,
                "building": st.session_state.building,
                "floor": str(st.session_state.floor),
                "map_address": st.session_state.map_address,
            }
        )

    with st.sidebar:
        st.header("Раздел")
        st.markdown(
            """
<style>
div[data-testid="stSidebar"] button[kind="secondary"] {
  width: 100%;
  justify-content: flex-start;
}
div[data-testid="stSidebar"] button.nav-active {
  opacity: 0.55;
}
</style>
""",
            unsafe_allow_html=True,
        )

        home_clicked = st.button("Главная",
                                 type="secondary", use_container_width=True)
        select_clicked = st.button(
            "Выбрать машину", type="secondary", use_container_width=True
        )

        if home_clicked:
            st.session_state.view = "home"
            _sync_query_params()
            st.rerun()
        if select_clicked:
            st.session_state.view = "select"
            _sync_query_params()
            st.rerun()

        # active_label = (
        #     "Главная" if st.session_state.view == "home"
        #     else "Выбрать машину"
        # )

        building_number = None
        floor_number = None
        map_address = None

        if st.session_state.view == "select":
            st.divider()
            st.header("Настройки")
            building_number = st.text_input(
                "Номер корпуса",
                key="building",
                on_change=_sync_query_params,
            )
            floor_number = st.number_input(
                "Этаж",
                min_value=1,
                max_value=13,
                key="floor",
                on_change=_sync_query_params,
            )
            map_address = st.text_input(
                "Адрес",
                key="map_address",
                on_change=_sync_query_params,
            )
            if st.button("Обновить"):
                st.rerun()

    if st.session_state.view == "home":
        render_machine_list(
            DEFAULT_API_BASE_URL,
            building=None,
            floor=1,
            show_all=True,
            cards_per_row=4,
        )
    else:
        cols = st.columns([2, 1])
        with cols[0]:
            render_machine_list(
                DEFAULT_API_BASE_URL,
                building=(building_number or "").strip(),
                floor=int(floor_number or 1),
                show_all=False,
                cards_per_row=2,
            )
        with cols[1]:
            st.subheader("Яндекс Карты")
            if map_address and map_address.strip():
                render_yandex_map(
                    map_address.strip(), width=560,
                    height=520, zoom=DEFAULT_MAP_ZOOM
                )
            else:
                st.info("Укажите адрес для карты в боковой панели.")


if __name__ == "__main__":
    main()
