# main file (frontend)
import json
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from src.external_api import map_widget_iframe_html
except ImportError:
    map_widget_iframe_html = None  # type: ignore


DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_MAP_CENTER = (55.751244, 37.618423)
DEFAULT_MAP_ZOOM = 10
DEFAULT_STATUS_ORDER = ["free", "busy",
                        "probably_free", "unavailable", "unknown"]


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
    data = request_json("GET", f"{DEFAULT_API_BASE_URL.rstrip('/')}/machines")
    if isinstance(data, list):
        return data
    return []


def submit_report(
    DEFAULT_API_BASE_URL: str, report_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    return request_json(
        "POST",
        f"{DEFAULT_API_BASE_URL.rstrip('/')}/report",
        headers={"Content-Type": "application/json"},
        data=json.dumps(report_data),
    )


def normalize_status(status_value: Any) -> str:
    if status_value is None:
        return "unknown"
    text = str(status_value).lower()
    if any(keyword in text for keyword in [
            "free", "available", "свободна", "idle"]):
        return "free"
    if any(
        keyword in text
        for keyword in ["busy", "process", "running", "занят", "в процессе"]
    ):
        return "busy"
    if any(keyword in text for keyword in [
            "probably_free", "скорее свободна"]):
        return "probably_free"
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


def status_sort_key(machine: Dict[str, Any]) -> int:
    status = normalize_status(
        machine.get("inferred_status")
        or machine.get("status")
        or machine.get("state")
        or machine.get("condition")
    )
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


def extract_time_remaining(machine: Dict[str, Any]) -> Optional[str]:
    for key in [
        "time_remaining",
        "time_left",
        "remaining_time",
        "time_to_end",
        "remaining",
        "left",
        "ends_in",
    ]:
        if key in machine and machine[key] is not None:
            return str(machine[key])
    if (
        machine.get("status")
        and isinstance(machine.get("status"), str)
        and "мин" in machine.get("status")
    ):
        return machine.get("status")
    return None


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
        if floor is None or abs(floor - selected_floor) <= 2:
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
    if selected_machine_id:
        st.markdown(f"**Машина #{selected_machine_id}**")

    machine_id = selected_machine_id or str(
        int(st.number_input("ID машины для отчета", min_value=1, value=1))
    )
    status = st.selectbox(
        "Статус машины",
        ["busy", "free", "unavailable"],
        format_func=lambda value: {
            "busy": "В процессе",
            "free": "Свободна",
            "unavailable": "Сломана",
        }[value],
    )

    time_remaining = None
    if status == "busy":
        time_remaining = st.number_input(
            "Время до конца (мин)", min_value=0, value=10)
    else:
        st.info("Время до конца используется только для статуса 'В процессе'.")

    if st.button("Отправить отчет"):
        if not machine_id.strip():
            st.warning("Укажите ID машины для отчета.")
        else:
            payload = {
                "machine_id": int(machine_id),
                "status": status,
                "time_remaining": time_remaining if status == "busy" else None,
            }
            result = submit_report(DEFAULT_API_BASE_URL, payload)
            if result is not None:
                st.success("Отчет отправлен успешно")
                st.json(result)


def render_machine_list(
    DEFAULT_API_BASE_URL: str, building: Optional[str], floor: int
) -> Optional[str]:
    machines = fetch_machines(DEFAULT_API_BASE_URL)
    if not machines:
        st.info("Нет данных о машинах. "
                "Проверьте URL бэкенда и доступность сервиса.")
        return None

    selected_floor_range = list(range(max(1, floor - 2), floor + 3))
    st.subheader(
        f"Машины на этажах {
            selected_floor_range[0]}–{selected_floor_range[-1]}"
    )

    filtered_machines = filter_and_sort_machines(machines, building, floor)
    if not filtered_machines:
        st.write("Нет машин на выбранных этажах или корпусах.")
        return None

    for machine in filtered_machines:
        machine_id = format_machine_name(machine)
        machine_floor = extract_floor(machine)
        machine_building = extract_building(machine)
        status_label = status_to_label(
            machine.get("inferred_status")
            or machine.get("status")
            or machine.get("state")
            or machine.get("condition")
        )
        time_remaining = extract_time_remaining(machine)

        row = st.container()
        cols = row.columns([2, 1, 1, 1, 1])
        cols[0].markdown(
            f"**#{machine_id}**\nТип: {
                machine.get('type', '—')}\nКорпус: {machine_building or '—'}"
        )
        cols[1].markdown(
            f"Этаж\n**{machine_floor if machine_floor is not None else '—'}**"
        )
        cols[2].markdown(f"Статус\n**{status_label}**")
        cols[3].markdown(f"Осталось\n**{time_remaining or '—'}**")
        if cols[4].button("Создать репорт", key=f"report_{machine_id}"):
            st.session_state.selected_report_machine = machine_id

    if "selected_report_machine" not in st.session_state:
        st.session_state.selected_report_machine = None

    if st.session_state.selected_report_machine:
        st.markdown("---")
        st.info(
            f"Создать репорт для машины: {
                st.session_state.selected_report_machine}"
        )
        render_report_panel(
            DEFAULT_API_BASE_URL, st.session_state.selected_report_machine
        )

    return st.session_state.selected_report_machine


def render_yandex_map(
        address: str, width: int, height: int, zoom: int) -> None:
    if map_widget_iframe_html is None:
        st.error(
            "Не удалось загрузить карту из external_api.py. "
            "Убедитесь, что модуль `src.external_api` "
            "и его зависимости доступны."
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
    st.set_page_config(page_title="SQR Safe And Sound", layout="wide")
    st.title("SQR Safe And Sound — фронтенд")
    st.markdown(
        "Введите корпус и этаж в сайдбаре, "
        "чтобы увидеть список машин на этажах N-2..N+2 "
        "и создать отчет для конкретной машины."
    )

    if "selected_report_machine" not in st.session_state:
        st.session_state.selected_report_machine = None

    with st.sidebar:
        st.header("Настройки")
        building_number = st.text_input("Номер корпуса (K)", value="1")
        floor_number = st.number_input(
            "Этаж (N)", min_value=1, max_value=100, value=1)
        map_address = st.text_input("Адрес для карты", value="Москва, Россия")
        zoom = st.slider(
            "Уровень масштабирования карты", 1, 18, DEFAULT_MAP_ZOOM)

    cols = st.columns([2, 1])
    with cols[0]:
        render_machine_list(
            DEFAULT_API_BASE_URL, building_number.strip(), floor_number)

    with cols[1]:
        st.subheader("Яндекс.Карта")
        if map_address.strip():
            render_yandex_map(
                map_address.strip(), width=560, height=520, zoom=zoom)
        else:
            st.warning("Укажите адрес для карты в боковой панели.")
            st.info(
                "Адрес будет использован для геокодирования "
                "через Yandex Geocoder в external_api.py."
            )


if __name__ == "__main__":
    main()
