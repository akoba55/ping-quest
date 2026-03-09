# Ping Quest

### インターネットを探検しよう

私たちは毎日インターネットを利用していますが、その通信が **世界のどこを通っているのか** を意識することは
ほとんどありません。

Ping Quest は、Ping や Traceroute を使って**インターネットの通信経路を世界地図上に可視化する教育ツール**です。

このツールを使うことで、次のようなことを体験できます。

* いつも使っている Web サイトはどこにあるのか
* 日本から海外のサイトへはどの国を経由するのか
* 通信はどこで海を越えるのか
* なぜ遠くのサーバほど通信が遅くなるのか
* なぜ有名なサイトは近くにあるのか

実際に調査しながら、**インターネットが世界中のネットワークとつながっていることを体験的に学びます。**

Ping Quest は、高校生向けのネットワーク体験授業や大学の初学者向けのネットワーク演習での利用を想定して開発されています。

Ping Quest is an educational tool that visualizes **ping** and **traceroute** results on a world map.
It helps students explore how Internet packets travel across the world by combining:

* traceroute results
* GeoIP location data
* ASN (Autonomous System Number) information
* RTT (network latency) measurements

The tool was originally developed as a **hands-on workshop for high school students or first-year university students** to experience the global structure of the Internet.

# What is Ping Quest?

When we access a website, packets travel through many routers across the Internet.
Ping Quest allows students to **observe and visualize that journey**.

Using this tool, students can:
* discover where a website is located
* observe how many routers are involved
* see how network latency increases with distance
* explore international network paths
* understand the uncertainty of GeoIP location estimation

The result is displayed on an interactive world map.

# Screenshot
## Example: Ping Result
Example showing the ping result and the estimated location of the destination server on the world map.

![Ping example](docs/images/ping_example.png)

## Example: Traceroute Visualization
Traceroute example showing multiple hops and international routing paths.

![Traceroute example](docs/images/tracert_example.png)

The visualization includes:
* hop-by-hop network path
* IP address and country
* RTT (latency) for each hop
* ASN and organization name
* GeoIP accuracy radius

# Educational Purpose

Ping Quest is designed for:
* high school outreach workshops
* introductory university networking classes
* cybersecurity education
* Internet measurement demonstrations

The tool encourages **exploration and inquiry-based learning**.

Students investigate questions such as:
* Where is a website physically located?
* How many routers are involved in reaching a server?
* At which hop does the traffic cross the ocean?
* Why are some hops slower than others?
* Why are GeoIP locations sometimes inaccurate?

# Features
* Execute `ping` and `traceroute`
* Visualize network routes on an interactive world map
* Display hop-by-hop RTT
* Show ASN and organization information
* Display GeoIP accuracy radius
* Highlight uncertainty of network path estimation
* Designed for educational workshops

# System Requirements
Python 3.9 or later

Required Python packages:
* streamlit
* folium
* pandas
* geoip2
* requests

Install dependencies:

```
pip install -r requirements.txt
```

---

# GeoIP Database
Ping Quest uses the **MaxMind GeoLite2 database**.
Download the free database from:
https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/
After downloading, place the files in the `data/` directory:

```
data/
 ├ GeoLite2-City.mmdb
 └ GeoLite2-ASN.mmdb
```

These files are **not included in the repository**.


# Running the Application

Start the Streamlit application:

```
streamlit run app/pingquest.py
```

Then open the browser:

```
http://localhost:8501
```

# Example Workshop Activity

Example tasks for students:

### Mission 1

Find where `google.com` is located.

### Mission 2

How many hops are required to reach YouTube?

### Mission 3

At which hop does the traffic cross the ocean?

### Mission 4

Which hop has the highest latency?

### Mission 5

Find a hop where the GeoIP location seems inaccurate.

Students analyze the results and discuss why the network path behaves that way.

# Known Limitations

Traceroute and GeoIP results are **estimations** and may not represent the exact physical network path.

Possible reasons include:

* ICMP rate limiting
* asymmetric routing
* MPLS tunnels
* Anycast routing
* GeoIP database inaccuracies

Understanding these limitations is part of the educational objective.


# Directory Structure

Example project structure:

```
ping-quest
│
├ README.md
├ requirements.txt
│
├ app
│   └ pingtrace_map.py
│
├ docs/images
│   └ ping_example.png
│   └ tracert_example.png
│
└ data
    └ GeoLite2 databases (not included)
```

# Intended Audience

Ping Quest is suitable for:

* high school students interested in the Internet
* introductory networking courses
* cybersecurity education programs
* outreach activities and workshops

# License

MIT License
