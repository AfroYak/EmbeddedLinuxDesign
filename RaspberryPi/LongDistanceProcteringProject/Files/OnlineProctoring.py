import HelperFunctions as HF
from gpiozero import LED, Button
from enum import Enum
from threading import Thread, Timer, Event
import time
import pickle
import cv2
import subprocess
import sys
import signal

# Hardware Setup
leds = [LED(23), LED(24), LED(17), LED(27), LED(22)]
pb = Button(pin=21, bounce_time=0.01)

device_email,device_password,server_password = HF.get_credentials()

instructor_email = 'CEN415Test1059305@gmail.com'
server_path = r'D:/ProjectUploads'

# Path Variables
current_date = None
path = None
image_path = None

# Establishing WebCam Connection
cap = cv2.VideoCapture(0)

# Initialising Global Variables
frame = None
out = None
report = None
times = None
time_exam_start = None

# Initialising Threads and Flags
thread_id = None
thread_email = None
thread_monitoring = None
thread_detecting = None
thread_blink = None
thread_upload = None
timer_exam = None
flag_monitoring = Event()
flag_detecting = Event()
flag_blink = Event()

# Student Information & Report
student_id = '1059305'
exam_time = 600

# Diagnostic Info
frame_count = 0


def initialise_variables():
    global current_date, path, image_path, frame, out, report, times, time_exam_start, thread_id, \
        thread_monitoring, thread_detecting, thread_blink, timer_exam, exam_time, frame_count

    current_date = HF.get_current_date()
    path = f'/home/pi/Desktop/Project/{current_date}'
    image_path = path + '/Images'
    HF.create_path(path)
    HF.create_path(image_path)

    frame = None
    out = None
    report = None
    times = [0, 0, 0, 0]  # [TotalTime, SingleFaceTime, MultiFaceTime, NoFaceTime]
    time_exam_start = None
    thread_id = None
    thread_monitoring = None
    thread_detecting = None
    thread_blink = None
    timer_exam = None
    frame_count = 0


class MainState(Enum):
    Idle_onEntry = 0
    Idle_onStay = 1
    CapturingFacePhoto_onEntry = 2
    CapturingFacePhoto_onStay = 3
    CapturingIDPhoto_onEntry = 4
    CapturingIDPhoto_onStay = 5
    CapturingEnvironment_onEntry = 6
    CapturingEnvironment_onStay = 7
    DetectingFace_onEntry = 8
    DetectingFace_onStay = 9
    SetupComplete_onEntry = 10
    SetupComplete_onStay = 11
    MonitoringStudent_onEntry = 12
    MonitoringStudent_onStay = 13
    GeneratingReport_onEntry = 14
    GeneratingReport_onStay = 15
    HandlingNewFootage_onEntry = 16
    HandlingNewFootage_onStay = 17
    PurgingOldFootage_onEntry = 18
    PurgingOldFootage_onStay = 19
    Cleanup_onEntry = 20
    Cleanup_onStay = 21


current_MainState = MainState.Idle_onEntry


class MonitoringState(Enum):
    SingleFace_onEntry = 0
    SingleFace_onStay = 1
    SingleFace_onExit = 2
    MultiFace_onEntry = 3
    MultiFace_onStay = 4
    MultiFace_onExit = 5
    NoFace_onEntry = 6
    NoFace_onStay = 7
    NoFace_onExit = 8
    Cleanup = 9


current_MonitoringState = MonitoringState.SingleFace_onStay


def pb_logic():
    global current_MainState, current_MonitoringState
    if current_MainState == MainState.Idle_onStay:
        current_MainState = MainState.CapturingFacePhoto_onEntry
    elif current_MainState == MainState.CapturingFacePhoto_onStay:
        current_MainState = MainState.CapturingIDPhoto_onEntry
    elif current_MainState == MainState.CapturingEnvironment_onStay:
        current_MainState = MainState.DetectingFace_onEntry
    elif current_MainState == MainState.SetupComplete_onStay:
        current_MainState = MainState.MonitoringStudent_onEntry
    elif current_MainState == MainState.MonitoringStudent_onStay:
        current_MainState = MainState.GeneratingReport_onEntry


pb.when_pressed = pb_logic


def monitoring_transition(i: int):
    global current_MonitoringState
    if i == 0:
        current_MonitoringState = MonitoringState.NoFace_onEntry
    elif i == 1:
        current_MonitoringState = MonitoringState.SingleFace_onEntry
    elif i > 1:
        current_MonitoringState = MonitoringState.MultiFace_onEntry


def update_times(index: int, start_time):
    times[index] += time.time() - start_time


def exam_finish():
    global current_MainState
    current_MainState = MainState.GeneratingReport_onEntry


def constant_detect(e: Event):
    while not e.isSet():
        HF.detect_faces(frame)

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)

## Monitoring Loop
def monitoring_fsm(flag: Event):
    # [TotalTime, SingleFaceTime, MultiFaceTime, NoFaceTime]
    global current_MonitoringState, times
    start_timer = time.time()
    picture_counter = [0, 0, 0]  # [SingleFace, MultiFace, NoFace]

    while not flag.isSet():
        num_faces = len(HF.faces)
        if current_MonitoringState == MonitoringState.SingleFace_onEntry:
            print('Single Face Detected')
            time_stamp = HF.gen_timestamp(time_exam_start)
            Thread(
                target=lambda: HF.save_image(frame, f"SingleFace_{picture_counter[0]}", image_path, time_stamp)).start()
            picture_counter[0] += 1
            current_MonitoringState = MonitoringState.SingleFace_onStay
            start_timer = time.time()

        elif current_MonitoringState == MonitoringState.SingleFace_onStay:
            if num_faces != 1:
                current_MonitoringState = MonitoringState.SingleFace_onExit

        elif current_MonitoringState == MonitoringState.SingleFace_onExit:
            update_times(1, start_timer)
            monitoring_transition(num_faces)

        elif current_MonitoringState == MonitoringState.MultiFace_onEntry:
            print('Multiple Faces Detected')
            time_stamp = HF.gen_timestamp(time_exam_start)
            Thread(
                target=lambda: HF.save_image(frame, f"MultiFace_{picture_counter[1]}", image_path, time_stamp)).start()
            picture_counter[1] += 1
            current_MonitoringState = MonitoringState.MultiFace_onStay
            start_timer = time.time()

        elif current_MonitoringState == MonitoringState.MultiFace_onStay:
            if num_faces <= 1:
                current_MonitoringState = MonitoringState.MultiFace_onExit

        elif current_MonitoringState == MonitoringState.MultiFace_onExit:
            update_times(2, start_timer)
            monitoring_transition(num_faces)

        elif current_MonitoringState == MonitoringState.NoFace_onEntry:
            print('No Face Detected')
            time_stamp = HF.gen_timestamp(time_exam_start)
            Thread(
                target=lambda: HF.save_image(frame, f"NoFace_{picture_counter[2]}", image_path, time_stamp)).start()
            picture_counter[2] += 1
            current_MonitoringState = MonitoringState.NoFace_onStay
            start_timer = time.time()

        elif current_MonitoringState == MonitoringState.NoFace_onStay:
            if num_faces != 0:
                current_MonitoringState = MonitoringState.NoFace_onExit

        elif current_MonitoringState == MonitoringState.NoFace_onExit:
            update_times(3, start_timer)
            monitoring_transition(num_faces)

    if current_MonitoringState == MonitoringState.SingleFace_onStay:
        update_times(1, start_timer)
    elif current_MonitoringState == MonitoringState.MultiFace_onStay:
        update_times(2, start_timer)
    elif current_MonitoringState == MonitoringState.NoFace_onStay:
        update_times(3, start_timer)


## MainLoop
while True:
    # print(f'Current MainState: {current_MainState} | Current Monitoring State: {current_MonitoringState} ')
    if current_MainState == MainState.Idle_onEntry:
        HF.turn_off_leds(leds)
        print('Press Button to Start Setup')
        current_MainState = MainState.Idle_onStay

    elif current_MainState == MainState.Idle_onStay:
        continue

    elif current_MainState == MainState.CapturingFacePhoto_onEntry:
        initialise_variables()
        HF.set_leds(leds, 0)
        print('Press Button to Capture Face')
        current_MainState = MainState.CapturingFacePhoto_onStay

    elif current_MainState == MainState.CapturingFacePhoto_onStay:
        _, frame = cap.read()

    elif current_MainState == MainState.CapturingIDPhoto_onEntry:
        HF.save_image(frame, "StudentPhoto", path)
        HF.set_leds(leds, 1)
        print('Present ID - Detecting ID')
        thread_id = Thread(target=lambda: HF.check_ID(student_id, cap, path))
        thread_id.start()
        current_MainState = MainState.CapturingIDPhoto_onStay

    elif current_MainState == MainState.CapturingIDPhoto_onStay:
        if not thread_id.is_alive():
            current_MainState = MainState.CapturingEnvironment_onEntry

    elif current_MainState == MainState.CapturingEnvironment_onEntry:
        print('Capturing Environment')
        HF.set_leds(leds, 2)
        thread_blink = Thread(target=lambda: HF.blink(leds[2], flag_blink, 0.2))
        thread_blink.start()
        out = cv2.VideoWriter(path + '/Environment.avi', cv2.VideoWriter_fourcc(*'XVID'), 24, (640, 480))
        current_MainState = MainState.CapturingEnvironment_onStay

    elif current_MainState == MainState.CapturingEnvironment_onStay:
        _, frame = cap.read()
        out.write(frame)

    elif current_MainState == MainState.DetectingFace_onEntry:
        out.release()
        HF.cleanup_thread(thread_blink, flag_blink)
        print('Detecting Face')
        HF.set_leds(leds, 3)
        thread_blink = Thread(target=lambda: HF.blink(leds[3], flag_blink, 0.2))
        thread_blink.start()
        current_MainState = MainState.DetectingFace_onStay

    elif current_MainState == MainState.DetectingFace_onStay:
        _, frame = cap.read()
        HF.detect_faces(frame)
        if len(HF.faces) > 0:
            current_MainState = MainState.SetupComplete_onEntry

    elif current_MainState == MainState.SetupComplete_onEntry:
        HF.cleanup_thread(thread_blink, flag_blink)
        print('Setup Complete - Press Button To Start')
        HF.set_leds(leds, 4)
        current_MainState = MainState.SetupComplete_onStay

    elif current_MainState == MainState.SetupComplete_onStay:
        continue

    elif current_MainState == MainState.MonitoringStudent_onEntry:
        print('Exam Started - Monitoring Student')
        thread_blink = Thread(target=lambda: HF.blink(leds[4], flag_blink, 0.2))
        thread_monitoring = Thread(target=lambda: monitoring_fsm(flag_monitoring))
        thread_detecting = Thread(target=lambda: constant_detect(flag_detecting))
        timer_exam = Timer(exam_time, exam_finish)

        thread_detecting.start()
        thread_blink.start()
        thread_monitoring.start()
        out = cv2.VideoWriter(path + '/Exam.avi', cv2.VideoWriter_fourcc(*'XVID'), 24, (640, 480))
        time_exam_start = time.time()

        timer_exam.start()
        current_MainState = MainState.MonitoringStudent_onStay

    elif current_MainState == MainState.MonitoringStudent_onStay:
        frame_count += 1
        _, frame = cap.read()
        out.write(frame)

    elif current_MainState == MainState.GeneratingReport_onEntry:
        out.release()
        timer_exam.cancel()
        HF.cleanup_thread(thread_monitoring, flag_monitoring)
        update_times(0, time_exam_start)
        HF.cleanup_thread(thread_blink, flag_blink)
        HF.cleanup_thread(thread_detecting, flag_detecting)
        report = HF.create_report(times,student_id)
        HF.save_text(report, path)
        print(report)
        print(f'Frame Count: {frame_count}')
        thread_email = Thread(target=lambda: HF.send_report(device_email, device_password, instructor_email, f'Exam: {current_date}',
                                             report))
        thread_email.start()
        current_MainState = MainState.GeneratingReport_onStay

    elif current_MainState == MainState.GeneratingReport_onStay:
        thread_email.join()
        current_MainState = MainState.HandlingNewFootage_onEntry

    elif current_MainState == MainState.HandlingNewFootage_onEntry:
        HF.turn_on_leds(leds)
        HF.upload_footage(server_password, path, server_path)
        current_MainState = MainState.HandlingNewFootage_onStay

    elif current_MainState == MainState.HandlingNewFootage_onStay:
        time.sleep(1)
        current_MainState = MainState.Idle_onEntry

    else:
        print('Error: Undefined Behaviour')
        break

print('Program Terminated')
