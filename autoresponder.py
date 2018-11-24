# Need more info? Check out the blogpost:
# how-to-make-a-bot-that-automatically-replies-to-comments-on-facebook-post

"""
NEED MORE INFO? CHECK OUT THE BLOGPOST
https://vandevliet.me/bot-automatically-responds-comments-facebook/
"""

import os
import sys
import signal
import mysql.connector
from time import sleep
import facebook
from PIL import Image
from io import BytesIO


APP_ID = os.environ['APP_ID']
APP_SECRET = os.environ['APP_SECRET']
PAGE_LONG_LIVED_ACCESS_TOKEN = os.environ['PAGE_LONG_LIVED_ACCESS_TOKEN']
PAGE_ID = os.environ['PAGE_ID']
POST_ID_TO_MONITOR = os.environ['POST_ID_TO_MONITOR']
ALBUM_ID_TO_POST_TO = os.environ['ALBUM_ID_TO_POST_TO']
MYSQL_USER = os.environ['MYSQL_USER']
MYSQL_PASSWORD = os.environ['MYSQL_PASSWORD']

COMBINED_POST_ID_TO_MONITOR = '%s_%s' % (PAGE_ID, POST_ID_TO_MONITOR)


def make_new_profile_pic(img):
    im = Image.open(BytesIO(img))
    im = im.resize((480, 480))

    # background version
    # background = Image.open("./fcdk_overlay.png")
    #
    # background.paste(im, (100, 100))

    # background.show()
    # bytes_array = BytesIO()
    # background.save(bytes_array, format='PNG')
    # bytes_array = bytes_array.getvalue()
    # return bytes_array

    # foreground version
    foreground = Image.open("./tgr_overlay.png")
    foreground = foreground.resize((250, 250))
    im = im.resize((250, 250))

    im.paste(foreground, (0, 0), foreground)

    # im.show()
    bytes_array = BytesIO()
    im.save(bytes_array, format='PNG')
    bytes_array = bytes_array.getvalue()
    return bytes_array


def comment_on_comment(graph, comment):
    comment_id = comment['id']

    print("Let's comment!")

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


def monitor_fb_comments():
    # create graph
    graph = facebook.GraphAPI(PAGE_LONG_LIVED_ACCESS_TOKEN)
    # that infinite loop tho
    print('I spy with my little eye...🕵️ ')
    while True:
        # print('I spy with my little eye...🕵️ ')
        sleep(5)

        # check mentions
        check_comments(graph, PAGE_ID, 'tagged')

        # check comments on page post
        check_comments(graph, COMBINED_POST_ID_TO_MONITOR, 'comments')


def check_comments(graph, id, type):
    # get the comments
    comments = graph.get_connections(id, type, order='chronological')

    for comment in comments['data']:
        print(comment['id'])

        # if we can't find it in our comments database, it means
        # we haven't commented on it yet
        if not Posts().get(comment['id']):
            comment_on_comment(graph, comment)

            # add it to the database, so we don't comment on it again
            Posts().add(comment['id'])

    # while there is a paging key in the comments, let's loop them and do exactly the same,
    # if you have a better way to do this, PRs are welcome :)
    while 'paging' in comments:
        comments = graph.get_connections(
            id, type, after=comments['paging']['cursors']['after'], order='chronological')

        for comment in comments['data']:
            print(comment['id'])

            if not Posts().get(comment['id']):
                comment_on_comment(graph, comment)
                Posts().add(comment['id'])


# Mary had a little class
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


# CTRL-C handler
def signal_handler(sig, frame):
    print('Bye!')
    sys.exit(0)


# add handler to exit gracefully
signal.signal(signal.SIGINT, signal_handler)

# started at the bottom, etc
if __name__ == '__main__':
    monitor_fb_comments()
