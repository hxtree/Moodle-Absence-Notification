#!/usr/bin/python
from datetime import datetime
import os
import json
import configparser
import MySQLdb
from pprint import pprint
from email.mime.text import MIMEText
import smtplib

def load_templates():
    for _file in os.listdir('templates'):
        with open('templates/' + _file) as data_file:
            filename = os.path.splitext(_file)[0]
            templates[filename] = json.load(data_file)
            # set a key in msgs array named after each template
            msgs[filename] = {}

def send_email(category, email_address, first_name, course_links):
    TO = email_address
    FROM = templates[category]['sender']
    CC = templates[category]['cc']
    html = templates[category]['message'].format(first_name=first_name,course_links=course_links)
    msg = MIMEText(
        html.encode('utf8'),
        'html'
    )
    msg['From'] = FROM
    msg['To'] = TO
    msg['CC'] = CC
    msg['Subject'] = templates[category]['subject']
    server = smtplib.SMTP('localhost')
    server.sendmail(FROM, TO, msg.as_string())
    server.quit()
    print('Emailed notification to ' + email_address)

def main():
    # get local run time
    runtime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # connect to Moodle database
    config = configparser.RawConfigParser()
    config.read('db.conf')

    db = MySQLdb.connect(
        host = config['database']['host'],
        user = config['database']['user'],
        passwd = config['database']['password'],
        db = config['database']['db']
    )
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    
    category_id = config['moodle']['semester_category_id']

    query = "SELECT \
            `mdl_course`.`id` AS `course_id`, \
            `mdl_course`.`shortname` AS `course_name`, \
            `mdl_user`.`email` AS `email_address`, \
            `mdl_user`.`firstname` AS `first_name`, \
            CASE \
                WHEN `mdl_role_assignments`.`roleid` = 1 THEN 'Manager' \
                WHEN `mdl_role_assignments`.`roleid` = 2 THEN 'Course creator' \
                WHEN `mdl_role_assignments`.`roleid` = 3 THEN 'Teacher' \
                WHEN `mdl_role_assignments`.`roleid` = 4 THEN 'Non-editing teacher' \
                WHEN `mdl_role_assignments`.`roleid` = 5 THEN 'Student' \
                WHEN `mdl_role_assignments`.`roleid` = 6 THEN 'Guest' \
                WHEN `mdl_role_assignments`.`roleid` = 7 THEN 'Authenticated user' \
            END AS `role`, \
            TIMESTAMPDIFF(DAY, FROM_UNIXTIME(`lastaccess`), NOW()) AS `days_since_access`, \
            FROM_UNIXTIME(`lastaccess`, '%m/%d/%Y') AS `last_access` \
        FROM `mdl_course` \
        LEFT OUTER JOIN `mdl_context` ON `mdl_course`.id = `mdl_context`.`instanceid` \
        LEFT OUTER JOIN `mdl_role_assignments` ON `mdl_context`.`id` = `mdl_role_assignments`.`contextid` \
        LEFT OUTER JOIN `mdl_user` ON `mdl_role_assignments`.`userid` = `mdl_user`.`id` \
        LEFT JOIN `mdl_user_lastaccess` ON `mdl_user_lastaccess`.`courseid` = `mdl_course`.`id` \
        WHERE `mdl_context`.`contextlevel` = '50' \
        AND TIMESTAMPDIFF(DAY, FROM_UNIXTIME(`lastaccess`), NOW()) > -1 \
        AND TIMESTAMPDIFF(DAY, FROM_UNIXTIME(`lastaccess`), NOW()) < 60 \
        AND `mdl_course`.`category` = '" + category_id + "' \
        GROUP BY  `mdl_user`.`id`,`mdl_course`.`id` \
        ORDER BY `role`,`lastaccess` DESC"
    cursor.execute(query)
    results = cursor.fetchall()

    # build array of email records for each template
    for row in results:
        for category, terms in templates.iteritems():
            if(row['role'] == terms['role']) and (row['days_since_access'] == terms['days_since_access']):
                # add record of student
                msgs[category][row['email_address']] = msgs[category].get(row['email_address'], {})
                msgs[category][row['email_address']]['first_name'] = row['first_name']
                # add courses record
                msgs[category][row['email_address']]['courses'] = msgs[category][row['email_address']].get('courses', {})
                msgs[category][row['email_address']]['courses'][row['course_id']] = row['course_name']

    course_link = "<li><a href=\"https://moodle.example.com/course/view.php?id={course_id}\">{course_name}</a></li>"

    # send each email record to email function as flat
    for category, msg in msgs.iteritems():
        #print category
        for email_address, record in msg.iteritems():
            first_name = record['first_name'].capitalize()
            course_links = ''
            for course_id,course_name in record['courses'].iteritems():
                course_links += course_link.format(course_id=course_id,course_name=course_name)
            send_email(category, email_address, first_name, course_links)

if __name__ == "__main__":
    msgs = {}
    templates = {}
    load_templates()

    main()
