# -*- coding: utf-8 -*-

import os
import sys
import signal
import mysql.connector
from time import sleep
import facebook
from PIL import Image
from io import BytesIO
import json
import base64
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import lxml.html
import smtplib
import urllib
import ssl
import yaml
import re
import traceback

APP_ID = os.environ['APP_ID']
APP_SECRET = os.environ['APP_SECRET']
PAGE_LONG_LIVED_ACCESS_TOKEN = os.environ['PAGE_LONG_LIVED_ACCESS_TOKEN']
PAGE_ID = os.environ['PAGE_ID']
POST_ID_TO_MONITOR = os.environ['POST_ID_TO_MONITOR']

MYSQL_USER = os.environ['MYSQL_USER']
MYSQL_PASSWORD = os.environ['MYSQL_PASSWORD']

NIMIQ_RPC_USER = os.environ['NIMIQ_RPC_USER']
NIMIQ_RPC_PASS = os.environ['NIMIQ_RPC_PASS']
NIMIQ_RPC_HOST = os.environ['NIMIQ_RPC_HOST']
NIMIQ_RPC_PORT = os.environ['NIMIQ_RPC_PORT']

GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

GMAIL_ADDRESS = os.environ['GMAIL_ADDRESS']
OAUTH_CLIENT_ID = os.environ['OAUTH_CLIENT_ID']
OAUTH_CLIENT_SECRET = os.environ['OAUTH_CLIENT_SECRET']
OAUTH_REFRESH_TOKEN = os.environ['OAUTH_REFRESH_TOKEN']
OAUTH_ACCESS_TOKEN = os.environ['OAUTH_ACCESS_TOKEN']

EMAIL_NOTIFICATION_ADDRESS = os.environ['EMAIL_NOTIFICATION_ADDRESS']


def generate_oauth2_string(username, access_token, as_base64=False):
    auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
    if as_base64:
        auth_string = base64.b64encode(
            auth_string.encode('ascii')).decode('ascii')
    return auth_string


def command_to_url(command):
    return '%s/%s' % (GOOGLE_ACCOUNTS_BASE_URL, command)


def call_refresh_token(client_id, client_secret, refresh_token):
    params = {}
    params['client_id'] = client_id
    params['client_secret'] = client_secret
    params['refresh_token'] = refresh_token
    params['grant_type'] = 'refresh_token'
    request_url = command_to_url('o/oauth2/token')
    response = urllib.urlopen(request_url, urllib.urlencode(
        params).encode('UTF-8')).read().decode('UTF-8')
    return json.loads(response)


def refresh_authorization(google_client_id, google_client_secret, refresh_token):
    response = call_refresh_token(
        google_client_id, google_client_secret, refresh_token)
    return response['access_token'], response['expires_in']


def send_mail(subject, message):
    access_token, expires_in = refresh_authorization(
        OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_REFRESH_TOKEN)
    auth_string = generate_oauth2_string(
        GMAIL_ADDRESS, access_token, as_base64=True)

    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = EMAIL_NOTIFICATION_ADDRESS
    msg.preamble = 'This is a multi-part message in MIME format.'
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)
    part_text = MIMEText(lxml.html.fromstring(
        message).text_content().encode('utf-8'), 'plain', _charset='utf-8')
    msg_alternative.attach(part_text)
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.ehlo(OAUTH_CLIENT_ID)
    server.starttls()
    server.docmd('AUTH', 'XOAUTH2 ' + auth_string)
    server.sendmail(GMAIL_ADDRESS, EMAIL_NOTIFICATION_ADDRESS, msg.as_string())
    server.quit()


def email_notification(message):
    send_mail("Facebook Tip Bot", message)


def comment_response(graph, comment):
    comment_id = comment['id']

    print("Responding to comment %d" % comment_id)

    # if the comment is not on the app page
    if not 'from' in comment:
        # like the comment
        # graph.put_like(object_id=comment_id)

        # ask to post on the app page
        graph.put_object(parent_object=comment_id,
                         connection_name='comments', message='Hey!')

        print('Asked to post on the app page')

        return

    comment_from_name = comment['from']['name']
    comment_from_id = comment['from']['id']
    comment_message = comment['message']
    profile = None

    # like the comment
    # graph.put_like(object_id=comment_id)

    # try to get first name, if it's a page there is not first_name
    try:
        profile = graph.get_object(
            comment_from_id, fields='first_name,last_name')
    except:
        pass

    # if it's a person that commented, we can use the first name
    if profile:
        graph.put_object(parent_object=comment_id, connection_name='comments',
                         message='Hi %s!' % (
                             profile['first_name'])
                         )
    else:
        graph.put_object(parent_object=comment_id, connection_name='comments',
                         message='Hi friend!'
                         )

    print('Responded to %s' % comment_from_name)


def check_comments(graph, id, type):
    # while there is a paging key in the comments, let's loop them
    comments = {}
    while True:
        # get the comments
        comments = graph.get_connections(
            id, type, after=comments['paging']['cursors']['after'] if 'paging' in comments else None, order='chronological')

        for comment in comments['data']:
            # if we can't find it in our comments database, it means
            # we haven't commented on it yet
            if not Posts().get(comment['id']):
                comment_response(graph, comment)

                # add it to the database, so we don't comment on it again
                Posts().add(comment['id'])

        if not 'paging' in comments:
            break


def json_rpc_fetch(method, *params):
    params = list(params)
    while len(params) > 0 and params[len(params) - 1] is None:
        params.pop()
    jsonrpc = json.dumps({
        "jsonrpc": "2.0",
        "id": 42,
        "method": method,
        "params": params
    })
    headers = {"Content-Length": str(len(jsonrpc))}
    headers["Authorization"] = "Basic " + \
        base64.b64encode(
            (NIMIQ_RPC_USER + ":" + NIMIQ_RPC_PASS).encode()).decode()
    response = requests.post("http://" + NIMIQ_RPC_HOST + ":" + NIMIQ_RPC_PORT,
                             data=jsonrpc, headers=headers)

    if response.status_code == 401:
        raise Exception(
            'Request Failed: Authentication Required. Status Code: ' + response.status_code)

    if response.status_code != 200:
        raise Exception('Request Failed. ' + ((response.status_message + ' - ')
                                              if response.status_message else "") + "Status Code: " + response.status_code)

    return json.loads(response.content.decode('utf-8'))["result"]


def amount_to_string(amount):
    amount = amount / settings["coin"]["inv_precision"]
    if amount % 1 != 0:
        return "{0:.5f}".format(amount)
    return str(amount)


def get_address(id):
    entry = Addresses().get(id)
    if not entry:
        result = json_rpc_fetch("createAccount")
        address = result["address"]
        Addresses().set(id, address)
    else:
        address = entry[0]
    return address


def get_balance(address, confirmations="latest"):
    balance = json_rpc_fetch("getBalance", address)
    if not confirmations is "latest":
        blockNumber = json_rpc_fetch("blockNumber")
        confirmations = blockNumber - confirmations
        for i in range(blockNumber, confirmations, -1):
            block = json_rpc_fetch("getBlockByNumber", i, True)
            for j in range(0, block.transactions.length):
                transaction = block["transactions"][j]
                # if transaction["fromAddress"] == address:
                #    balance -= transaction["value"] + transaction["fee"]
                if transaction["toAddress"] == address:
                    balance -= transaction["value"]
    return balance


def dump_error(err):
    return "dump_error:\nException: " + str(err) + "\nStacktrace:\n====================\n" + traceback.format_exc()


class Posts:
    def __init__(self):
        self.connection = mysql.connector.connect(
            host='localhost', database='facebook_tip_bot', user=MYSQL_USER, password=MYSQL_PASSWORD)
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS comments (id TEXT NOT NULL, PRIMARY KEY (id(128)))")

    def get(self, id):
        self.cursor.execute("SELECT * FROM comments where id='%s'" % id)

        row = self.cursor.fetchone()

        return row

    def add(self, id):
        try:
            self.cursor.execute("INSERT INTO comments VALUES('%s')" % id)
            lid = self.cursor.lastrowid
            self.connection.commit()
            return lid
        except mysql.connector.IntegrityError:
            return False


class Addresses:
    def __init__(self):
        self.connection = mysql.connector.connect(
            host='localhost', database='facebook_tip_bot', user=MYSQL_USER, password=MYSQL_PASSWORD)
        self.cursor = self.connection.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS addresses (id TEXT NOT NULL, address VARCHAR(44) NOT NULL, PRIMARY KEY (id(128)))")

    def get(self, id):
        self.cursor.execute("SELECT address FROM addresses where id='%s'" % id)

        row = self.cursor.fetchone()

        return row

    def set(self, id, address):
        try:
            self.cursor.execute(
                "INSERT INTO addresses VALUES('%s', '%s')" % (id, address))
            lid = self.cursor.lastrowid
            self.connection.commit()
            return lid
        except mysql.connector.IntegrityError:
            return False


# CTRL-C handler
def signal_handler(sig, frame):
    print('\nBye!')
    sys.exit(0)


# check if the config file exists
if not os.path.isfile("./settings.yml"):
    print(
        "Configuration file doesn't exist! Please read the README.md file first."
    )
    sys.exit(1)

# load settings
with open('./settings.yml', 'r') as infile:
    settings = yaml.safe_load(infile)

MINER_FEE = settings["coin"]["miner_fee"] * settings["coin"]["inv_precision"]
MIN_WITHDRAW = settings["coin"]["min_withdraw"] * \
    settings["coin"]["inv_precision"]
MIN_TIP = settings["coin"]["min_tip"] * settings["coin"]["inv_precision"]

# connect to coin daemon
print("Connecting to " + settings["coin"]["full_name"] + " RPC API...")

try:
    blockNumber = json_rpc_fetch("blockNumber")
    # TODO: check if the node is fully synced
    if not blockNumber:
        sys.exit(1)
except Exception as err:
    email_notification(dump_error(err))
    print("Couldn't get blockNumber " + err)
    sys.exit(1)

try:
    balance = get_balance(
        "NQ50 V2LA 91XE SJTE DHT5 122G KFTV C6T6 8QAQ"
    )
    print(
        "Connected to JSON RPC API. Current total balance is " +
        amount_to_string(balance) + " " + settings["coin"]["short_name"]
    )
except Exception as err:
    email_notification(dump_error(err))
    print("Couldn't get wallet balance " + str(err))
    sys.exit(1)

# enable SSL for email notifications
ssl._create_default_https_context = ssl._create_unverified_context

# add handler to exit gracefully
signal.signal(signal.SIGINT, signal_handler)

# create api graph
graph = facebook.GraphAPI(PAGE_LONG_LIVED_ACCESS_TOKEN)

# facebook doesn't notify when comments are recived so we have to pull that data constantly
print('Started monitoring facebook comments...')
while True:
    sleep(5)

    # check mentions
    check_comments(graph, PAGE_ID, 'tagged')

    # check comments on page post
    check_comments(graph, '%s_%s' % (PAGE_ID, POST_ID_TO_MONITOR), 'comments')
