from gpiozero import LED, Button
from datetime import datetime
import time
from enum import Enum
from threading import Thread, Timer, Event
import signal
import sys
import cv2
import os
import pytesseract
import pickle
import smtplib
import os

face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
faces = None
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587


def create_path(p):
    try:
        os.makedirs(p)
    except FileExistsError:
        pass


def set_leds(x: list, y: int):
    for i, led in enumerate(x):
        if i == y:
            led.on()
            continue
        led.off()


def turn_off_leds(leds: list):
    for led in leds:
        led.off()

def turn_on_leds(leds: list):
    for led in leds:
        led.on()


def blink(led, event, t):
    while not event.isSet():
        led.on()
        time.sleep(t)
        led.off()
        time.sleep(t)


def get_current_date():
    today = datetime.now()
    current_date = today.strftime("%d-%m-%Y--%H-%M-%S")
    return current_date


def save_image(frame, filename, path, text=""):
    cv2.putText(
        frame,
        text,
        (10, 50),  # position at which writing has to start
        cv2.FONT_HERSHEY_SIMPLEX,  # font family
        1,  # font size
        (209, 80, 0, 255),  # font color
        2)  # font stroke
    cv2.imwrite(path + '/' + filename + '.jpg', frame)


def detect_faces(frame):
    global faces
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.05, 15)


def check_ID(student_id, cap, path):
    while True:
        _, frame = cap.read()
        text = pytesseract.image_to_string(frame)
        if student_id in text:
            save_image(frame, filename='StudentID', path=path, text='')
            break


def gen_timestamp(initial_time):
    timestamp = time.time() - initial_time
    time_struct = time.gmtime(timestamp)
    return f'{time_struct[3]}:{time_struct[4]}:{time_struct[5]}'


def update_time(times, begin_time, label):
    interval = time.time() - begin_time
    times[label] += interval
    begin_time = time.time()


def create_report(times, student_id):
    return f'''
    Report for {student_id}
    Total Time : {times[0]:.2f} Seconds
    Single Face Percentage: {(times[1] / times[0]) * 100:.2f}%
    Multi-Face Percentage: {(times[2] / times[0]) * 100:.2f}%
    No-Face Percentage: {(times[3] / times[0]) * 100:.2f}%
        '''


def cleanup_thread(thread: Thread, flag: Event):
    flag.set()
    thread.join()
    flag.clear()


def send_report(user, password, recipient, subject, text):
    try:
        smtpserver = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.ehlo()

        smtpserver.login(user, password)
        header = 'To:' + recipient + '\n' + 'From: ' + user
        header = header + '\n' + 'Subject:' + subject + '\n'
        msg = header + '\n' + text + ' \n\n'
        smtpserver.sendmail(user, recipient, msg)
        smtpserver.close()
    except Exception:
        print('Error')


def upload_footage(password, local_path, destination_path):
    os.system(f'sshpass -p {password} scp -r {local_path}/ upload_server:{destination_path}')
    print('Upload Complete')


def get_credentials():
    f = open('creds.pickle', 'rb')
    credentials = pickle.load(f)
    f.close()
    return credentials['email'],credentials['password'],credentials['dkpw']

def save_text(report, path):
    f = open(f'{path}/Report.txt','w+')
    f.write(report)
    f.close()

# def save_video(filename, f, video_flag):
#     out = cv2.VideoWriter(path + '/' + filename + '.avi', cv2.VideoWriter_fourcc(*'XVID'), 24, (640, 480))
#     while not video_flag.isSet():
#         out.write(f)
#     out.release()
