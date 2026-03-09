"""
Ping Quest Tool

2026.03.09
"""

APP_HELP = """\
Ping Quest

Usage:
  This application must be started with Streamlit.  
  streamlit run app/pingquest.py -- [options]
  
Options:
  -h, --help              Show this help message and exit
  --geoip-dir PATH        Directory containing GeoLite2-City.mmdb and GeoLite2-ASN.mmdb
                          Default: current directory
  --map-home-lat FLOAT    Initial map center latitude
                          Default: 35.681236 (Tokyo Station)
  --map-home-lon FLOAT    Initial map center longitude
                          Default: 139.767125 (Tokyo Station)

Examples:
  streamlit run app/pingquest.py
  streamlit run app/pingquest.py -- --geoip-dir ./data
  streamlit run app/pingquest.py -- --map-home-lat 35.681236 --map-home-lon 139.767125
"""

import argparse
import folium
import subprocess
import re
import geoip2.database
import pandas as pd
from urllib.parse import urlparse
import ipaddress
import random
import requests
import os
import sys
from pathlib import Path
import streamlit as st
from streamlit.components.v1 import html
from streamlit.runtime.scriptrunner import get_script_run_ctx
import urllib3.util.connection as urllib3_cn
import socket
from folium.plugins import PolyLineTextPath


TEXT = {
    "title": {
        "ja": "インターネットを探検しよう!!",
        "en": "Explore the Internet!!",
    },
    "subtitle": {
        "ja": "Ping / Traceroute の結果を世界地図に表示します。",
        "en": "Visualize ping and traceroute results on a world map. Please input target host.",
    },
    "target": {"ja": "接続先ホスト", "en": "Target host"},
    "source": {"ja": "接続元IPアドレス", "en": "Source IP address"},
    "command": {"ja": "実行するコマンド", "en": "Command"},
    "start_ping": {"ja": "Ping開始", "en": "Start Ping"},
    "finish_ping": {"ja": "Ping完了", "en": "Ping Finished"},
    "start_trace": {"ja": "Traceroute開始", "en": "Start Traceroute"},
    "finish_trace": {"ja": "Traceroute完了", "en": "Traceroute Finished"},
    "input_destination": {
        "ja": "宛先とするURL,ドメイン,IPアドレスを入力してください。",
        "en": "Please input destination url, domain or ip address",
    },
    "result": {"ja": "Ping / Traceroute 結果", "en": "Ping / Traceroute Result"},
    "return": {"ja": "戻る", "en": "Return"},
    "clear": {"ja": "クリア", "en": "Clear"},
    "guidance": {
        "ja": "「Ping開始」もしくは「Traceroute開始」ボタンを押下してください。",
        "en": 'Please enter "Start Ping" or "Start Traceroute" botton.',
    },
}


class Params:
    APP_NAME = "Ping Quest"
    # Default map center (Tokyo Station)
    DEFAULT_MAP_HOME_LAT = 35.681236
    DEFAULT_MAP_HOME_LON = 139.767125
    # GeoIP database file names
    CITY_DB_NAME = "GeoLite2-City.mmdb"
    ASN_DB_NAME = "GeoLite2-ASN.mmdb"
    # Map settings
    DEFAULT_ZOOM_LEVEL = 3
    # UI
    PING_COMMAND = "ping"
    # 名前解決なし、待ち時間1000ms
    TRACEROUTE_COMMAND = "tracert /d /w 1000"
    # 利用する外部サイト：送信元IPアドレスの特定 or 描画用国旗アイコン
    GET_SOURCE_URL = "https://ifconfig.me/ip"
    GET_FLAGICON_URL = "https://flagcdn.com/w20/"


def allowed_gai_family():
    """
    socket.getaddrinfo() が返すアドレスファミリーを
    IPv4 (AF_INET) のみに制限します。
    IPV6対応は、別途実施
    """
    family = socket.AF_INET
    return family


def multiple_location(lat, lon, location):
    # 複数IPで同一のロケーションを示した場合に表示が重なることを回避
    if [lat, lon] in location:
        lat += random.uniform(-0.01, 0.01)
        lon += random.uniform(-0.01, 0.01)
        lat, lon = multiple_location(lat, lon, location)

    return lat, lon


def rtt_to_color(rtt):
    if rtt is None:
        return "#888888"
    if rtt < 30:
        return "#888888"
    elif rtt < 100:
        return "#9999FF"
    elif rtt < 200:
        return "#0000FF"
    else:
        return "#FF0000"


def is_ip(addr: str) -> bool:
    try:
        ipaddress.ip_address(addr)
        return True
    except ValueError:
        return False


def run_ping(host, hops, city_db, asn_db):
    logs = ""
    st.session_state.running = True

    log_area = st.empty()
    ip_pattern = re.compile(r"\s+(?:\[)?(\d+\.\d+\.\d+\.\d+)(?:\])?\s+")
    rtt_pattern = re.compile(r"Average\s\=\s(\d+)ms")
    process = subprocess.Popen(
        ["cmd", "/c", f"chcp 437 >nul && {Params.PING_COMMAND}", "-4", host],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="shift_jis",
    )
    if process:
        data = {}
        for line in process.stdout:
            if line != "\n":
                logs += line.strip() + "\n"  # テキストをどんどん追加
                log_area.text(logs)  # 全体を再描画
            else:
                continue

            ip_m = ip_pattern.search(line)
            rtt_m = rtt_pattern.search(line)
            if ip_m:
                ip = ip_m.group(1)
                data = read_database(ip, city_db, asn_db)
                data["Hop"] = 1

            if rtt_m:
                data["RTT"] = (
                    float(rtt_m.group(1)) if rtt_m.group(1) is not None else None
                )

        if data:
            hops.append(data)

        process.wait()

    return hops


def run_traceroute(host, hops, city_db, asn_db):
    logs = ""

    log_area = st.empty()
    ip_pattern = re.compile(r"^\s*(\d+).*\s+(?:\[)?(\d+\.\d+\.\d+\.\d+)(?:\])?")
    rtt_pattern = re.compile(r"\s+(\d+)\s*ms")

    process = subprocess.Popen(
        [
            "cmd",
            "/c",
            f"chcp 437 >nul && {Params.TRACEROUTE_COMMAND}",
            "-4",
            host,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="shift_jis",
    )
    if process:
        for line in process.stdout:
            data = {}
            if line != "\n":
                logs += line.strip() + "\n"  # ← テキストをどんどん追加
                log_area.text(logs)  # ← 全体を再描画
            else:
                continue

            ip_m = ip_pattern.search(line)
            rtt_m = rtt_pattern.findall(line)

            if ip_m:
                ip = ip_m.group(2)
                data = read_database(ip, city_db, asn_db)
                data["Hop"] = ip_m.group(1)

            if rtt_m:
                # rtts = map(int, rtt_m)
                rtts = [int(i) for i in rtt_m]
                data["RTT"] = round(float(sum(rtts) / len(rtts)), 2)

            if ip_m:
                hops.append(data)

        process.wait()

    return hops


def read_database(ip, city_db, asn_db):
    data = init_data()
    data["IP"] = ip
    limit = 30

    try:
        r = city_db.city(ip)
        data["Country"] = (
            r.country.iso_code if r.country.name is not None else "unknown"
        )
        data["City"] = r.city.name if r.city.name is not None else "unknown"
        data["lat"] = (
            r.location.latitude if r.location.latitude is not None else float(0)
        )
        data["lon"] = (
            r.location.longitude if r.location.longitude is not None else float(0)
        )
        data["accuracy"] = (
            r.location.accuracy_radius
            if r.location.accuracy_radius is not None
            else float(0)
        )

        try:
            r2 = asn_db.asn(ip)
            data["asn"] = r2.autonomous_system_number
            data["org"] = r2.autonomous_system_organization
            if len(data["org"]) > limit:
                # '...'の分を考慮してスライス
                data["org"] = data["org"][: limit - 3] + "..."

        except Exception:
            print(f"Cannot Find data from {ip} on ASN_DB")
            # continue
    except Exception:
        print(f"Cannot Find data from {ip} on CITY_DB")

    return data


def get_sourceip():
    ip = None
    # urllib3の名前解決の挙動を変更
    # この変更により、このコードを実行した後に行われる全てのrequestsはIPv4を優先（実質強制）
    urllib3_cn.allowed_gai_family = allowed_gai_family

    # 変更後、requests.get() を実行
    try:
        ip = requests.get(GET_SOURCE_URL, timeout=3).text.strip()

    except requests.exceptions.RequestException as e:
        print(f"リクエスト中にエラーが発生しました: {e}")

    return ip


def run_folium(hops):
    setlocations = []

    m = folium.Map(
        location=[HOME_LAT, HOME_LON],
        zoom_start=Params.DEFAULT_ZOOM_LEVEL,
        tiles="Cartodb Positron",
        world_copy_jump=False,
    )

    FORMAT_HTML_POP = '<font size="4" face="Terminal" color="{color}"><ul><li>Hop Count: {hop_num}</li><li>Country: {ctry}</li><li>Organization: {org}</li><li>IP: {ip}</li><li>City: {city}</li><li>RTT: {rtt} ms</li><li>Accuracy: {acc} km</li></ul></font>'
    FORMAT_HTML_TIP = '<img src="{src}" /><b><font size="4" face="Terminal" color="{color}"> {count}<br>{org}</font></b>'

    # 経度が-25から-180の範囲にある場合には、太平洋側で地図を作成するため、経度をシフトする
    last_lon = 140

    def shift_lon(lon, last_lon):
        #        print(f"before {lon},{last_lon}")
        if abs(lon - last_lon) > abs(lon + 360 - last_lon):
            lon += 360
        last_lon = lon
        #        print(f"after {lon},{last_lon}")
        return lon, last_lon

    for i, hop in enumerate(hops):

        if "lat" in hop and "lon" in hop:
            if hop["lat"] == "unknown" or hop["lat"] is None:
                continue
            if hop["lat"] == 0 and hop["lon"] == 0:
                continue

            if hop["Country"]:
                png = f"{GET_FLAGICON_URL}{hop['Country'].lower()}.png"
            else:
                png = f"{GET_FLAGICON_URL}un.png"

            pophtml = FORMAT_HTML_POP.format(
                color="black",
                hop_num=hop["Hop"],
                ip=hop["IP"],
                city=hop["City"],
                ctry=hop["Country"],
                rtt=hop["RTT"],
                org=hop["org"],
                acc=hop["accuracy"],
            )
            accuracy_km = hop["accuracy"]
            accuracy_m = accuracy_km * 1000

            popup = folium.Popup(pophtml, max_width=600)
            tooltiphtml = FORMAT_HTML_TIP.format(
                src=png, color="black", org=hop["org"], count=hop["Hop"]
            )
            tooltip = folium.Tooltip(tooltiphtml)
            try:
                custom_icon = folium.CustomIcon(png, icon_size=(30, 20))
            except:
                custom_icon = folium.Icon(color="blue", icon="info-sign")

            # 位置の重なりを考慮して重なっていた場合は緯度経度を+-0.01の範囲でずらす
            lat_h, lon_h = multiple_location(hop["lat"], hop["lon"], setlocations)
            hops[i]["lon"], last_lon = shift_lon(lon_h, last_lon)
            folium.Marker(
                [lat_h, hops[i]["lon"]],
                popup=popup,
                tooltip=tooltip,
                icon=custom_icon,
                fill=True,
                fill_opacity=0.8,
            ).add_to(m)
            # accuracy を円形で表示
            folium.Circle(
                location=[lat_h, hops[i]["lon"]],
                radius=accuracy_m,
                color="blue",
                fill=True,
                fill_opacity=0.05,
                weight=1,
                stroke=False,
            ).add_to(m)

            setlocations.append([lat_h, lon_h])
            # ホップ数がある場合
            if (
                i > 0
                and hops[i - 1]["lat"] != "unknown"
                and hops[i]["lat"] != "unknown"
            ):
                # 直近のポイントと今回のポイントが0でないこと
                if hops[i - 1]["lat"] != 0 and hops[i]["lat"] != 0:
                    color = rtt_to_color(hop["RTT"])

                    line = folium.PolyLine(
                        (
                            [hops[i - 1]["lat"], hops[i - 1]["lon"]],
                            [hops[i]["lat"], hops[i]["lon"]],
                        ),
                        color=color,
                        weight=10,
                        opacity=0.2,
                    ).add_to(m)
                    if hop["RTT"] != 0:
                        # color = rtt_to_color(hop["RTT"])
                        PolyLineTextPath(
                            line,
                            f"{hop['RTT']:.0f} ms",
                            repeat=False,
                            center=True,
                            attributes={
                                "fill": "red",
                                "font-size": "16",
                                "font-weight": "bold",
                                "dy": -6,
                                "stroke": "none",
                                "repeat": False,
                                "center": True,
                            },
                        ).add_to(m)

    map_html = m.get_root().render()
    html(map_html, height=600)

    return


def init_data():
    data = {}
    for i in ["Hop", "IP", "Country", "City", "asn", "org"]:
        data[i] = "unknown"

    for i in ["lat", "lon", "accuracy", "RTT"]:
        data[i] = float(0)

    return data


def clear_input():
    st.session_state.target_host = ""
    st.session_state.run_state = ""
    st.session_state.running = False


def restart():
    st.session_state.run_state = ""
    st.session_state.running = False


def numeric(df):
    numeric_cols = ["Hop", "RTT", "lat", "lon", "accuracy"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.round({"RTT": 2, "lat": 4, "lon": 4})
    df["asn"] = df["asn"].astype(str)
    return df


def main():
    lang = st.sidebar.selectbox("Language", ["English", "日本語"])
    lang = "en" if lang == "English" else "ja"

    hops = []
    city_db = geoip2.database.Reader(CITY_DB)
    asn_db = geoip2.database.Reader(ASN_DB)
    st.session_state.setdefault("running", False)
    st.session_state.setdefault("target_host", "")
    st.session_state.setdefault("run_state", "")

    st.set_page_config(page_title="Ping Quest", layout="wide")
    st.title(f"🌏 {TEXT['title'][lang]}")

    st.info(f"{TEXT['subtitle'][lang]}")

    def go_ping():
        st.session_state.run_state = "ping"
        st.session_state.running = True

    def go_trace():
        st.session_state.run_state = "trace"
        st.session_state.running = True

    col1, col2, col3, col4 = st.columns([4, 1, 2, 1])
    with col1:
        target = st.text_input(
            TEXT["input_destination"][lang],
            key="target_host",
            placeholder="example.com or 8.8.8.8 or https://example.com/abc...",
        )
    with col2:
        st.button(
            TEXT["start_ping"][lang],
            on_click=go_ping,
            disabled=st.session_state.running,
        )
    with col3:
        st.button(
            TEXT["start_trace"][lang],
            on_click=go_trace,
            disabled=st.session_state.running,
        )
    with col4:
        st.button(TEXT["return"][lang], on_click=restart)

    if target:
        st.button(TEXT["clear"][lang], on_click=clear_input)

        if is_ip(target):
            host = target
        elif urlparse(target).hostname:
            host = urlparse(target).hostname
        else:
            host = target

        sip = get_sourceip()
        if sip:
            data = read_database(sip, city_db, asn_db)
            data["Hop"] = 0
            data["RTT"] = float(0)
            hops.append(data)

        if (
            st.session_state.run_state == "ping"
            or st.session_state.run_state == "trace"
        ):
            st.info(
                f"{TEXT['guidance'][lang]}\n- {TEXT['target'][lang]}：{host} \n - {TEXT['source'][lang]}：{sip}\n - {TEXT['command'][lang]}：{st.session_state.run_state}\n"
            )
        else:
            st.info(
                f"{TEXT['guidance'][lang]}\n- {TEXT['target'][lang]}：{host} \n - {TEXT['source'][lang]}：{sip}\n"
            )

        if st.session_state.run_state == "ping":
            hops = run_ping(host, hops, city_db, asn_db)
            hops_df = pd.DataFrame(hops)

            st.dataframe(hops_df)
            hops_df = numeric(hops_df)
            print(hops_df)
            # df が traceroute 結果などの DataFrame として
            if hops:
                run_folium(hops)
            st.success(f"{TEXT["finish_ping"][lang]} ✅")
            st.session_state.running = False
            st.session_state.run_state = ""

        if st.session_state.run_state == "trace":
            hops = run_traceroute(host, hops, city_db, asn_db)
            hops_df = pd.DataFrame(hops)
            hops_df = numeric(hops_df)
            st.dataframe(hops_df)
            print(hops_df)
            if hops:
                run_folium(hops)
            st.success(f"{TEXT["finish_trace"][lang]} ✅")
            st.session_state.running = False
            st.session_state.run_state = ""

    city_db.close()
    asn_db.close()


def argv_check():
    parser = argparse.ArgumentParser(
        prog="pingquest.py",
        add_help=False,
        description="Ping Quest: visualize ping/traceroute results on a world map.",
    )

    parser.add_argument(
        "--geoip-dir",
        type=str,
        default=".",
        help="Directory containing GeoLite2-City.mmdb and GeoLite2-ASN.mmdb "
        "(default: current directory or GEOIP_DIR).",
    )
    parser.add_argument(
        "--map-home-lat",
        type=float,
        default=Params.DEFAULT_MAP_HOME_LAT,
        help="Default map center latitude " "(default: Tokyo Station or MAP_HOME_LAT).",
    )

    parser.add_argument(
        "--map-home-lon",
        type=float,
        default=Params.DEFAULT_MAP_HOME_LON,
        help="Default map center longitude "
        "(default: Tokyo Station or MAP_HOME_LON).",
    )

    args, _ = parser.parse_known_args()

    geoip_dir = args.geoip_dir or os.environ.get("GEOIP_DIR")
    map_home_lat = args.map_home_lat or os.environ.get("MAP_HOME_LAT")
    map_home_lon = args.map_home_lon or os.environ.get("MAP_HOME_LON")

    return (geoip_dir, map_home_lat, map_home_lon)


def early_cli_check() -> None:
    if get_script_run_ctx() is None:
        print(APP_HELP)
        raise SystemExit(0)

    if "--help" in sys.argv or "-h" in sys.argv:
        st.info(APP_HELP)
        print(APP_HELP)
        st.stop()
        raise SystemExit(0)


def run_once():
    GEOIP_DIR, HOME_LAT, HOME_LON = argv_check()
    CITY_DB = f"{GEOIP_DIR}/{Params.CITY_DB_NAME}"
    ASN_DB = f"{GEOIP_DIR}/{Params.ASN_DB_NAME}"
    GET_SOURCE_URL = Params.GET_SOURCE_URL
    GET_FLAGICON_URL = Params.GET_FLAGICON_URL

    if not "initialized" in st.session_state:

        st.session_state.initialized = True

        early_cli_check()

        print(
            f"GeoIP directory: {GEOIP_DIR}\n"
            f"Home position(lat,lot): {HOME_LAT}, {HOME_LON}\n"
            f"City databse: {CITY_DB}\n"
            f"Asn databse: {ASN_DB}\n"
        )

        city_db = Path(CITY_DB)
        asn_db = Path(ASN_DB)

        if not city_db.exists():
            st.error(f"{Params.CITY_DB_NAME} not found")
            st.code(str(city_db))
            st.info(
                "Download GeoLite2 database from MaxMind (https://dev.maxmind.com/geoip/geolite2-free-geolocation-data)."
            )
            st.stop()

        if not asn_db.exists():
            st.error(f"{Params.ASN_DB_NAME} not found")
            st.code(str(asn_db))
            st.info(
                "Download GeoLite2 database from MaxMind (https://dev.maxmind.com/geoip/geolite2-free-geolocation-data)."
            )
            st.stop()

    return (CITY_DB, ASN_DB, GET_SOURCE_URL, GET_FLAGICON_URL, HOME_LAT, HOME_LON)


if __name__ == "__main__":
    CITY_DB, ASN_DB, GET_SOURCE_URL, GET_FLAGICON_URL, HOME_LAT, HOME_LON = run_once()
    main()
