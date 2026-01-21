import secrets

from dns import DNSServer
from storage import Storage
from web import WebServer, RefuseHttpsServer
from display import DisplayController

import network
import uasyncio as asyncio


# Wi-Fi AP setup
ap = network.WLAN(network.AP_IF)
ap.config(essid=secrets.SSID, password=secrets.PASSWORD)
ap.active(True)

# Wi-Fi STA setup
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect(secrets.STA_SSID, secrets.STA_PASSWORD)

# SPI and OLED setup
display_controller = DisplayController()

# Initialize storage
storage = Storage()

# Initialize web server
web_server = WebServer(storage, sta)
refuse_server = RefuseHttpsServer()

# Initialize dns server
dns_server = DNSServer(ip=ap.ifconfig()[0])


async def main():
    ip = ap.ifconfig()[0]

    # Show QR code with Wi-Fi credentials
    display_controller.show_qr_code(ip, secrets.SSID, secrets.PASSWORD)

    # start servers and display cycle
    await asyncio.gather(
        web_server.start(),
        refuse_server.start(),
        display_controller.start_display_cycle(),
        dns_server.start(),
    )

# Run async main
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print("Fatal error:", e)
    finally:
        ap.active(False)
        sta.active(False)
