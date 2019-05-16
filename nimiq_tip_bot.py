# -*- coding: utf-8 -*-

import os
import sys
import signal
import mysql.connector
from time import sleep
import facebook
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
from random import randint
from flask import Flask, request
from dotenv import load_dotenv

# automatically search and load the enviroment variables in .env
load_dotenv()

# check if the config file exists
if not os.path.isfile("./settings.yml"):
    print(
        "Configuration file doesn't exist! Please read the README.md file first."
    )
    sys.exit(1)

# load settings
with open('./settings.yml', 'r') as infile:
    settings = yaml.safe_load(infile)

MINER_FEE = int(round(settings["coin"]["miner_fee"]
                      * settings["coin"]["inv_precision"]))
MIN_WITHDRAW = int(round(settings["coin"]["min_withdraw"] *
                         settings["coin"]["inv_precision"]))
MIN_TIP = int(round(settings["coin"]["min_tip"]
                    * settings["coin"]["inv_precision"]))

APP_ID = os.environ['APP_ID']
APP_SECRET = os.environ['APP_SECRET']
APP_VERIFY_TOKEN = os.environ['APP_VERIFY_TOKEN']
PAGE_LONG_LIVED_ACCESS_TOKEN = os.environ['PAGE_LONG_LIVED_ACCESS_TOKEN']
PAGE_ID = os.environ['PAGE_ID']
POST_ID_TO_MONITOR = os.environ['POST_ID_TO_MONITOR']

DATABASE_HOST = os.environ['DATABASE_HOST']
DATABASE_USER = os.environ['DATABASE_USER']
DATABASE_PASS = os.environ['DATABASE_PASS']

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


def post_comment(id, message):
    # get the random tag
    d = settings["coin"]["random_length"]
    n = 10 ** d - 1
    r = ("0.%0" + str(d) + "d") % randint(0, n)
    tag = "[" + settings["coin"]["random_suffix"] + r + "]"

    # post message with random tag at the end
    graph.put_object(parent_object=id, connection_name='comments',
                     message=message + " " + tag)


def process_comment(graph, comment):
    id = comment['id']

    full_message = comment['message']
    from_id = None
    from_name = None

    # like the comment
    # graph.put_like(object_id=id)

    # try to get the name
    try:
        from_id = comment['from']['id']
        from_name = graph.get_object(from_id, fields='name')['name']
    except:
        pass

    if not from_id:
        print("Response to comment %s" % id)
        post_comment(id, 'Hi friend! You might want to re-post here ' +
                         "https://www.facebook.com/permalink.php?story_fbid=" + POST_ID_TO_MONITOR + "&id=" + PAGE_ID)
        print("Asked to re-post on page")
        return

    # if comment is from the page ignore it
    if from_id == PAGE_ID:
        return

    print("Response to comment %s" % id)
    print("User has id %s" % from_id)

    match = re.search("(!.*)", full_message)

    if not match:
        # forward to notification email
        print("Message forwarded to email notification")
        email_notification("message " + id + ":\n" + full_message)
        return

    message = match.group()

    match = re.search("^!(\\S+)", message)
    if not match:
        # forward to notification email
        print("Message forwarded to email notification")
        email_notification("message " + id + ":\n" + full_message)
        return

    command = match.group(1)

    print("Processing command " + command)

    # commands
    if command == "balance":
        print("Requesting balance")
        try:
            address = get_address(from_id)
            balance = get_balance(
                address,
                settings["coin"]["min_confirmations"]
            )
            unconfirmed_balance = get_balance(address)
            unconfirmed_balance -= balance

            print("Balance is " + amount_to_string(balance) + (" ( Unconfirmed: " +
                                                               amount_to_string(unconfirmed_balance) + " )" if unconfirmed_balance > 0 else ""))
            post_comment(id, "Your current balance is " + amount_to_string(balance) + " $" + settings["coin"]["short_name"] + "." + (
                " ( Unconfirmed: " + amount_to_string(unconfirmed_balance) + " $" + settings["coin"]["short_name"] + " )" if unconfirmed_balance > 0 else ""))

        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id, "Could not get your balance.")
            print("Error in !balance command" + str(err))

    elif command == "address":
        print("Requesting address")
        try:
            address = get_address(from_id)
            post_comment(id,
                         "Your deposit address is " + address)
            print("Sending address")

        except Exception as err:
            email_notification(dump_error(err))
            post_comment(
                id, "I'm sorry, something went wrong while getting the address.")
            print("Something went wrong while getting the address " + str(err))

    elif command == "tip":
        to_id = None
        to_name = None
        match = None

        message_tags = graph.get_object(id, fields='message_tags')[
            'message_tags']
        for message_tag in message_tags:
            test_name = re.escape(message_tag["name"])
            match = re.search(
                "^.?tip (" + test_name + ") ([\\d\\.]+)", message)
            if match:
                to_id = message_tag["id"]
                to_name = message_tag["name"]
                break

        print("Processing tip for %s" % from_id)

        if not match or len(match.groups()) < 2:
            post_comment(id, "Usage: <!tip [user] [amount]>")
            return

        try:
            amount = int(round(float(match.group(2)) *
                               settings["coin"]["inv_precision"]))
        except Exception as err:
            post_comment(id, "I'm sorry, The amount is invalid")
            print(from_id + " tried to send an invalid amount")
            return

        print(
            "from: " + from_name + " to: " + to_name +
            " amount: " + amount_to_string(amount)
        )

        # check the user isn't tipping themselves.
        if to_id == from_id:
            post_comment(id, "I'm sorry, You can't tip yourself !")
            print(from_id + " tried to send to themselves.")
            return

        # check amount is larger than minimum tip amount
        # charge twice the miner fee and send a half with the tip for withdrawal
        if amount < MIN_TIP:
            post_comment(id,
                         "I'm sorry, your tip to " +
                         to_name +
                         " (" +
                         amount_to_string(amount) +
                         " $" +
                         settings["coin"]["short_name"] +
                         ") is smaller that the minimum amount allowed (" +
                         amount_to_string(MIN_TIP) +
                         " $" +
                         settings["coin"]["short_name"] +
                         ")")
            print(from_id + " tried to send too small of a tip.")
            return

        # check balance with min. confirmations
        from_address = None
        to_address = None
        balance = None
        try:
            from_address = get_address(from_id)
            balance = get_balance(
                from_address,
                settings["coin"]["min_confirmations"]
            )
        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "Could not get your balance.")
            print("Error while checking balance for " + from_id + str(err))
            return

        try:
            # charge twice the miner fee and send a half with the tip for withdrawal
            if balance >= amount + 2 * MINER_FEE:
                to_address = get_address(to_id)
                json_rpc_fetch("sendTransaction", {
                    'from': from_address,
                    'to': to_address,
                    'value': amount + MINER_FEE,  # send the withdrawal fee with the tip
                    'fee': MINER_FEE
                })
                post_comment(id,
                             from_name +
                             " tipped " +
                             to_name +
                             " " +
                             amount_to_string(amount) +
                             " $" +
                             settings["coin"]["short_name"] +
                             " Reply !help to this page post to claim your tip !")
                print(from_id +
                      " tipped " +
                      to_id +
                      " " +
                      amount_to_string(amount) +
                      " " +
                      settings["coin"]["short_name"]
                      )
            else:
                short = amount + 2 * MINER_FEE - balance
                post_comment(id,
                             "I'm sorry, you dont have enough funds (you are short " +
                             amount_to_string(short) +
                             " $" +
                             settings["coin"]["short_name"] +
                             ")")
                print(from_id +
                      " tried to tip " +
                      to_id +
                      " " +
                      amount_to_string(amount) +
                      ", but has only " +
                      balance
                      )
        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "Could not send coins to " + to_name)
            print("Error while sending coins from " +
                  from_name + " to " + to_name + str(err))

    elif command == "withdraw":
        print("Processing withdrawal")
        match = re.search(
            "^.?withdraw (" + settings["coin"]["address_pattern"] + ")", message)
        if not match:
            post_comment(id,
                         "Usage: <!withdraw [" +
                         settings["coin"]["full_name"] +
                         " address]>"
                         )
            return

        to_address = match.group(1)
        from_address = None
        balance = None

        try:
            if not json_rpc_fetch("getAccount", to_address):
                post_comment(id,
                             "I'm sorry, " + to_address + " is invalid.")
                print(
                    "%s tried to withdraw to an invalid address" %
                    from_id
                )
                return

        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "I'm sorry, something went wrong with the address validation for " +
                         to_address)
            print(
                from_id + " tried to withdraw but something went wrong " +
                str(err)
            )
            return

        try:
            from_address = get_address(from_id)
            balance = get_balance(
                from_address,
                settings["coin"]["min_confirmations"]
            )
        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "I'm sorry I could not get your balance"
                         )
            return

        if balance < MIN_WITHDRAW + MINER_FEE:
            short = MIN_WITHDRAW + MINER_FEE - balance
            post_comment(id,
                         "I'm sorry, the minimum withdrawal amount is " +
                         amount_to_string(MIN_WITHDRAW) +
                         " $" +
                         settings["coin"]["short_name"] +
                         " you are short " +
                         amount_to_string(short) +
                         " $" +
                         settings["coin"]["short_name"])
            print(
                from_id +
                " tried to withdraw " +
                amount_to_string(balance) +
                ", but min is set to " +
                amount_to_string(MIN_WITHDRAW)
            )
            return

        if balance < MIN_WITHDRAW + MINER_FEE:
            short = MIN_WITHDRAW + MINER_FEE - balance
            post_comment(id,
                         "I'm sorry, you dont have enough funds to cover the miner fee (you are short " +
                         amount_to_string(short) +
                         " $" +
                         settings["coin"]["short_name"] +
                         ")")
            print(
                from_id +
                " tried to withdraw " +
                amount_to_string(balance) +
                ", but funds don't cover the miner fee " +
                amount_to_string(MINER_FEE)
            )
            return

        try:
            amount = balance - MINER_FEE
            json_rpc_fetch("sendTransaction", {
                'from': from_address,
                'to': to_address,
                'value': amount,
                'fee': MINER_FEE
            })
            post_comment(id,
                         amount_to_string(amount) +
                         " $" +
                         settings["coin"]["short_name"] +
                         " has been withdrawn from your account to " +
                         to_address)
            print(
                "Sending " +
                amount_to_string(amount) +
                " " +
                settings["coin"]["full_name"] +
                " to " +
                to_address +
                " for " +
                from_id
            )

        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "Could not send coins to " + to_address)
            print("Error in !withdraw command" + str(err))

    elif command == "send":
        print("Processing transaction")
        match = re.search(
            "^.?send (" + settings["coin"]["address_pattern"] + ") ([\\d\\.]+)", message)
        if not match:
            post_comment(
                id, "Usage: <!send [" + settings["coin"]["full_name"] + " address] [amount]>")
            return

        to_address = match.group(1)
        from_address = None
        balance = None

        try:
            amount = int(round(float(match.group(2)) *
                               settings["coin"]["inv_precision"]))
        except Exception as err:
            post_comment(id, "I'm sorry, The amount is invalid")
            print(from_id + " tried to send an invalid amount")
            return

        try:
            if not json_rpc_fetch("getAccount", to_address):
                post_comment(id,
                             "I'm sorry, " + to_address + " is invalid.")
                print(
                    "%s tried to withdraw to an invalid address" %
                    from_id
                )
                return

        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "I'm sorry, something went wrong with the address validation for " +
                         to_address)
            print(
                from_id + " tried to withdraw but something went wrong " + str(err))
            return

        try:
            from_address = get_address(from_id)
            balance = get_balance(
                from_address, settings["coin"]["min_confirmations"])
        except Exception as err:
            email_notification(dump_error(err))
            post_comment(id,
                         "I'm sorry I could not get your balance"
                         )
            return

        if balance >= amount + MINER_FEE:
            if amount >= MIN_WITHDRAW + MINER_FEE:
                try:
                    json_rpc_fetch("sendTransaction", {
                        'from': from_address,
                        'to': to_address,
                        'value': amount,
                        'fee': MINER_FEE
                    })
                    post_comment(id,
                                 amount_to_string(amount) +
                                 " $" +
                                 settings["coin"]["short_name"] +
                                 " has been sent from your account to " +
                                 to_address)
                    print(
                        "Sending " +
                        amount_to_string(amount) +
                        " " +
                        settings["coin"]["full_name"] +
                        " to " +
                        to_address +
                        " for " +
                        from_id
                    )

                except Exception as err:
                    email_notification(dump_error(err))
                    post_comment(id,
                                 "Could not send coins to " + to_address)
                    print("Error in !send command", err)

            else:
                short = MIN_WITHDRAW + MINER_FEE - amount
                post_comment(id,
                             "I'm sorry, the minimum amount is " +
                             amount_to_string(MIN_WITHDRAW) +
                             " $" +
                             settings["coin"]["short_name"] +
                             " you are short " +
                             amount_to_string(short) +
                             " $" +
                             settings["coin"]["short_name"])
                print(
                    from_id +
                    " tried to send " +
                    amount_to_string(balance) +
                    ", but min is set to " +
                    amount_to_string(MIN_WITHDRAW)
                )

        else:
            short = amount + MINER_FEE - balance
            post_comment(id,
                         "I'm sorry, you dont have enough funds (you are short " +
                         amount_to_string(short) +
                         " $" +
                         settings["coin"]["short_name"] +
                         ")")
            print(
                from_id +
                " tried to send " +
                amount_to_string(amount) +
                " to " +
                to_id +
                ", but has only " +
                balance
            )

    elif command == "help":
        post_comment(
            id, "Here is a list of commands: !balance !send !tip !withdraw !address")

    else:
        # if command doesnt match return
        post_comment(id, "I'm sorry, I don't recognize that command")
        print("Command not recognized")


def check_comments(graph, id, type):
    # queue comments for processing
    queue = []
    result = {}
    while True:
        # get one comment at a time in reverse chronological order (newest first)
        result = graph.get_connections(
            id, type, after=result['paging']['cursors']['after'] if 'paging' in result else None, order='reverse_chronological', limit=1)
        data = result["data"]
        comment = data[0]

        # queue comment if not in database
        # exit if already stored
        if Posts().get(comment['id']):
            break
        else:
            queue.append(comment)

        # exit if there are no more pages to process
        if not 'paging' in result:
            break

    # process commands in queue in chronological order (oldest first)
    for comment in reversed(queue):
        process_comment(graph, comment)

        # add it to the database, so we don't comment on it again
        Posts().add(comment['id'])


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
    amount = amount / float(settings["coin"]["inv_precision"])
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
            for j in range(0, len(block["transactions"])):
                transaction = block["transactions"][j]
                # if transaction["fromAddress"] == address:
                #    balance -= transaction["value"] + transaction["fee"]
                if transaction["toAddress"] == address:
                    balance -= transaction["value"]
    return int(round(balance))


def dump_error(err):
    return "dump_error:\nException: " + str(err) + "\nStacktrace:\n====================\n" + traceback.format_exc()


class Posts:
    def __init__(self):
        self.connection = mysql.connector.connect(
            host=DATABASE_HOST, database='facebook_tip_bot', user=DATABASE_USER, password=DATABASE_PASS)
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
            host=DATABASE_HOST, database='facebook_tip_bot', user=DATABASE_USER, password=DATABASE_PASS)
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


# connect to coin daemon
print("Connecting to " + settings["coin"]["full_name"] + " RPC API...")

try:
    blockNumber = json_rpc_fetch("blockNumber")
    # TODO: check if the node is fully synced
    if not blockNumber:
        sys.exit(1)
except Exception as err:
    email_notification(dump_error(err))
    print("Couldn't get blockNumber " + str(err))
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

# start app to handle webhook
app = Flask(__name__)


@app.route('/', methods=['GET'])
def handle_verification():
    '''
    Verifies facebook webhook subscription
    Successful when verify_token is same as token sent by facebook app
    '''
    if (request.args.get('hub.verify_token', '') == APP_VERIFY_TOKEN):
        print("succefully verified")
        return request.args.get('hub.challenge', '')
    else:
        print("Wrong verification token!")
        return "Wrong validation token"


@app.route('/', methods=['POST'])
def handle_message():
    '''
    Handle messages sent by facebook messenger to the applicaiton
    '''
    data = request.get_json()

    print(data)

    '''
    if data["object"] == "page":
        # check mentions
        check_comments(graph, PAGE_ID, 'tagged')

        # check comments on page post
        check_comments(graph, '%s_%s' %
                       (PAGE_ID, POST_ID_TO_MONITOR), 'comments')

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):

                    sender_id = messaging_event["sender"]["id"]
                    recipient_id = messaging_event["recipient"]["id"]
                    message_text = messaging_event["message"]["text"]
                    send_message_response(
                        sender_id, parse_user_message(message_text))
    '''

    return "ok"


if __name__ == "__main__":
    app.run(host='localhost', port=7000)

'''
{
  "field": "mention",
  "value": {
    "post_id": "44444444_444444444",
    "sender_name": "Example Name",
    "item": "post",
    "sender_id": "44444444",
    "verb": "add"
  }
}

{
  "entry":[
    {
      "changes":[
        {
          "field":"mention",
          "value":{
            "sender_name":"Example Name",
            "post_id":"44444444_444444444",
            "verb":"add",
            "sender_id":"44444444",
            "item":"post"
          }
        }
      ],
      "id":"0",
      "time":1543608880
    }
  ],
  "object":"page"
}

{
  "field": "feed",
  "value": {
    "item": "status",
    "post_id": "44444444_444444444",
    "verb": "add",
    "published": 1,
    "created_time": 1543608367,
    "message": "Example post content.",
    "from": {
      "name": "Test Page",
      "id": "1067280970047460"
    }
  }
}

{
  "entry":[
    {
      "changes":[
        {
          "field":"feed",
          "value":{
            "from":{
              "name":"Test Page",
              "id":"1067280970047460"
            },
            "item":"status",
            "post_id":"44444444_444444444",
            "verb":"add",
            "published":1,
            "created_time":1543608842,
            "message":"Example post content."
          }
        }
      ],
      "id":"0",
      "time":1543608843
    }
  ],
  "object":"page"
}
'''
