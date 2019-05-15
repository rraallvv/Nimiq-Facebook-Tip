Nimiq-Facebook-Tip is an open-source Python Facebook bot for tipping with altcoins. It's integrated with the Nimiq blockchain but it can be easily modified for other altcoins. 

# Installation
To install Nimiq-Facebook-Tip simply clone this repo and install the dependencies:
```
$ git clone https://github.com/rraallvv/Nimiq-Facebook-Tip
$ cd Nimiq-Facebook-Tip
$ pip install -r requirements.txt
```

# Configuration file
After installation proceed to the configuration file `settings.yml`.

## rpc
JSON RPC API connection info.
* **host** - Daemon hostname (`localhost` if hosted on the same machine)
* **port** - Daemon RPC port (by default `8648` for Nimiq)

## coin
Basic coin settings.
* **min_withdraw** - Minimum amount of coins to withdraw
* **min_confirmations** - Minimum amount of confirmations for the current balance needed to tip/withdraw coins
* **min_tip** - Minimum amount of coins to tip
* **short_name** - Short name for the coin (e.g. `NIM`)
* **full_name** - Full name for the coin (e.g. `Nimiq`)
* **inv_precision** - Inverse of the smalest amount (e.g. 1/0.00001 or 1e5 for Nimiq)
* **miner_fee** - Fee charged on transactions to cover up the miner fees.
* **address_pattern** - The regex pattern to match in the comment when searching for the address to send/withdraw
* **random_prefix** - Prefix added to the random stamp (used to fool Facebook into thinking each comment is different) 
* **random_length** - Number of decimals of the random number in the random stamp

# Environment variables
The following environment variables are needed for Nimiq-Facebook-Tip to work. On Unix compatible systems those can be added to the files `./.env`, `~/.bashrc`, `~/.profile` or `~/.bash_profile`.
```
# Facebook app
APP_ID=<Facebook app id>
APP_SECRET=<Facebook app secret>
APP_VERIFY_TOKEN=<Facebook app verification token>
PAGE_LONG_LIVED_ACCESS_TOKEN=<Facebook page access token>
PAGE_ID=<Facebook page id>
POST_ID_TO_MONITOR=<post id on Facebook where all tips will be posted>
# Nimiq jsonrpc client
NIMIQ_RPC_USER=<nimiq jsonrpc user>
NIMIQ_RPC_PASS=<nimiq jsonrpc password>
NIMIQ_RPC_HOST=<server address>
NIMIQ_RPC_PORT=<server port>
# Database
DATABASE_HOST=<server address>
DATABASE_USER=<database user>
DATABASE_PASS=<database password>
# Email notifications
GMAIL_ADDRESS=<sender email>
OAUTH_CLIENT_ID=<gmail API client id>
OAUTH_CLIENT_SECRET=<gmail API secret id>
OAUTH_REFRESH_TOKEN=<gmail API refresh token>
OAUTH_ACCESS_TOKEN=<gmail API access token>
EMAIL_NOTIFICATION_ADDRESS=<recipient email>
```

# How does it work?
Nimiq-Facebook-Tip creates a Nimiq address for every Facebook user. Then it moves the amount of coins from one account to the other, or to some external address for withdrawals.

# How to run it?
Before running the bot, you have to be running a node on the Nimiq blockchain with JSON-RPC API enabled. JSON-RPC can be enabled using a configuration file with the settings below:
```
{
  protocol: "dumb",
  type: "light",
  rpcServer: {
    enabled: "yes",
    port: 8648,
    username: "<rpc user>",
    password: "<rpc password>"
  }
}
```
To start the server put those in a file (e.g. `settings.conf`) and run `node ./clients/nodejs/index.js --config=settings.conf`

Then, to run Nimiq-Facebook-Tip execute the command `python nimiq_tip_bot.py` in the directory where you cloned this repository.

## Commands

Instructions are executed by messaging the bot on Facebook with one of the following commands preceded by an exclamation mark.

| **Command** | **Arguments**     | **Description**
|-------------|-------------------|--------------------------------------------------------------------
| `address`   |                      | Displays the Nimiq address where you can send your funds to for the tip bot.
| `balance`   |                      | Displays your current wallet balance.
| `help`      |                      | Displays a help message with the list of available commands.
| `send`      | `<address> <amount>` | Sends the specified amount of coins to the specified address.
| `tip`       | `<user> <amount>`    | Sends the specified amount of coins to the specified Facebook user's tag.
| `withdraw`  | `<address>`          | Withdraws your entire balance to the specified Nimiq address.

## Examples

**@NimiqB** !balance

**@NimiqB** !tip **@someuser** 5

**@NimiqB** !send NQ40 7G2N J5FN 51MV 95DG FCQ9 ET11 DVMV QR1F 5

**@NimiqB** !withdraw NQ40 7G2N J5FN 51MV 95DG FCQ9 ET11 DVMV QR1F

## Use random comments if needed

If Facebook shows a message complaining about you posting the same comand multiple times, simply add some random caracters at the end of the comment like in the examples below. In the examples the caracters **"fwrh34iuhf"** put after the required parameters are simply ignored by the bot.

**@NimiqB** !balance fwrh34iuhf

**@NimiqB** !tip **@someuser** 5 fwrh34iuhf

**@NimiqB** !send NQ40 7G2N J5FN 51MV 95DG FCQ9 ET11 DVMV QR1F 5 fwrh34iuhf

**@NimiqB** !withdraw NQ40 7G2N J5FN 51MV 95DG FCQ9 ET11 DVMV QR1F fwrh34iuhf

## Important

For the bot to be able to read your comands they have to be public.

## ~~Beer~~ Coffee Fund 😄

If you like the Facebook bot please donate some NIM 
```
NQ40 7G2N J5FN 51MV 95DG FCQ9 ET11 DVMV QR1F
```
