import time
import sys
import getpass
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions

USER = "asinghan"
PASS = getpass.getpass()
COOKIE_FILE = "cookie.dat"

options = FirefoxOptions()
options.add_argument("--headless")
driver = webdriver.Firefox(options=options)

print("Loading 25Live", file=sys.stderr)
driver.get("https://25live.collegenet.com/pro/cmu")

print("Waiting for authentication page", file=sys.stderr)
time.sleep(10)

if driver.current_url.startswith("https://login.cmu.edu/idp/profile/SAML2/Redirect/SSO"):
    print("Need to authenticate", file=sys.stderr)
    time.sleep(3)

    driver.find_element_by_id("username").send_keys(USER)
    driver.find_element_by_id("passwordinput").send_keys(PASS)
    driver.find_element_by_class_name("loginbutton").click()

    time.sleep(3)

print("Waiting for redirect", file=sys.stderr)
while not driver.current_url.startswith("https://25live.collegenet.com"):
    time.sleep(0.1)

print("25Live found", file=sys.stderr)

with open(COOKIE_FILE, "w+") as f:
    f.write(driver.get_cookie("WSSESSIONID")["value"])

driver.quit()
