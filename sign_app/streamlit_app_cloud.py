import streamlit as st
import copy
import cv2
import numpy as np
import pandas as pd
from random import randrange
import mediapipe as mp
from tensorflow import device
from google.cloud import storage
from keras.models import load_model
from tensorflow import config
import os
from google.oauth2 import service_account
import av
from PIL import Image
from streamlit_webrtc import (
    RTCConfiguration,
    VideoProcessorBase,
    WebRtcMode,
    webrtc_streamer,
)

config.run_functions_eagerly(True)
option = " "

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:relay.metered.ca:80",
                          "turn:relay.metered.ca:80",
                          "turn:relay.metered.ca:443",
                          "turn:relay.metered.ca:443?transport=tcp"],
                 "username":"fde6cbb36d18c153785bf733",
                 "credential":"bEuNDxnIvdtIPPvB"}]}
)
list_of_predictions = []
# counter = 0
def app_sign_language_detection(model, mp_model):
    class signs(VideoProcessorBase):
        def __init__(self) -> None:

            ## alterando ppara carregar os modelos antes de chamar a função
            self.model = model
            self.hands = mp_model


        def draw_and_predict(self, image):
            prediction_list = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["del", "space"]
            print(f'initial print after defining function')
            # print(image)
            image = cv2.flip(image, 1)
            debug_image = copy.deepcopy(image)

            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.hands.process(image)
            # print(results.multi_hand_landmarks)
            cropped_image = None
            shape = 0

            if results.multi_hand_landmarks is not None:
                for hand_landmarks in results.multi_hand_landmarks:
                    brect = calc_bounding_rect(debug_image, hand_landmarks)
                    debug_image = draw_bounding_rect(debug_image, brect)
                    cropped_image = debug_image[brect[3]:brect[2], brect[1]:brect[0]]
            else:
                print('No hand found')

            try:
                cropped_image = cv2.resize(cropped_image, (56, 56))
                cropped_image = backgroud_removal(cropped_image)
                cropped_image = cropped_image/255
                cropped_image = cropped_image.reshape(1, 56, 56, 3)
            except:
                print('No hand found')

            predict = None
            # global counter
            # if counter % 10 != 0:
            #     return debug_image
            global top3
            try:

                if cropped_image.shape == (1, 56, 56, 3):
                    print('entered if shape statement')
                    predict = self.model.predict(cropped_image)[0]
                    global list_of_predictions
                    list_of_predictions.append(predict)
                    if len(list_of_predictions) > 5:
                        del list_of_predictions[0]
                    predict_mean = np.mean(np.array(list_of_predictions), axis = 0)
                    top3 = np.argsort(predict_mean)[-3:]
                    top3 = list(reversed(top3))
                    debug_image = print_prob([predict_mean[i] for i in top3], [prediction_list[i] for i in top3], debug_image)
                return debug_image
            except:
                cv2.putText(debug_image, f"No hand detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)
                return debug_image

        def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
            # global counter
            # counter += 1
            image = frame.to_ndarray(format='rgb24')
            annotated_image = self.draw_and_predict(image)
            return av.VideoFrame.from_ndarray(annotated_image,format='rgb24')

    webrtc_ctx = webrtc_streamer(
        key="sign_language",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        video_processor_factory=signs,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
        )


@st.cache_resource
def load_cloud_model():
    bucket_name = st.secrets["BUCKET"]
    model_name = st.secrets["MODEL_NAME"]
    model_dir = st.secrets["MODEL_DIR"]

    credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
    # Create a client object for Google Cloud Storage
    client = storage.Client(credentials=credentials)

    # Get a bucket object for the bucket
    bucket = client.get_bucket(bucket_name)

    # Get a blob object for the Keras model file
    blob = bucket.blob(model_name)

    # Download the Keras model file to a local file
    blob.download_to_filename(model_dir + model_name)

    model = load_model(model_dir + model_name)

    return model


@st.cache_resource
def load_mediapipe_model():
    max_num_hands = 1
    min_detection_confidence = 0.5
    min_tracking_confidence = 0.5

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=max_num_hands,
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
    )
    return hands


def calc_bounding_rect(image, hand_landmarks):
    h, w, c = image.shape
    x_max = 0
    y_max = 0
    x_min = w
    y_min = h
    for lm in hand_landmarks.landmark:
        x, y = int(lm.x * w), int(lm.y * h)
        if x > x_max:
            x_max = x
        if x < x_min:
            x_min = x
        if y > y_max:
            y_max = y
        if y < y_min:
            y_min = y

    y_min -= round(h/20)
    y_max += round(h/20)
    x_min -= round(w/20)
    x_max += round(w/20)

    x_max, x_min, y_max, y_min = make_image_square(x_max, x_min, y_max, y_min, h, w)
    return [x_max, x_min, y_max, y_min]

def make_image_square(x_max, x_min, y_max, y_min, h, w):
    '''used in calculating bounding rect'''
    x_diff = x_max - x_min
    y_diff = y_max - y_min

    if y_diff > x_diff:

        length_diff =  y_diff - x_diff

        half_length_diff_max = round(length_diff/2)
        half_length_diff_min = length_diff-half_length_diff_max

        x_max = half_length_diff_max + x_max
        x_min = x_min - half_length_diff_min

    elif x_diff > y_diff:
        length_diff =  x_diff -  y_diff

        half_length_diff_max = round(length_diff/2)
        half_length_diff_min = length_diff-half_length_diff_max

        y_max = half_length_diff_max + y_max
        y_min = y_min - half_length_diff_min
    return x_max, x_min, y_max, y_min

def draw_bounding_rect(image, brect):
    cv2.rectangle(image, (brect[1], brect[3]), (brect[0], brect[2]),
        (0, 255, 0), 2)

    return image


def backgroud_removal(img):
    """Receives the croped image and proceeds
    to remove the background, leaving only the hand layout.
    """
    if img.shape[2] < 3:
        return img
    # initialize mediapipe
    mp_selfie_segmentation = mp.solutions.selfie_segmentation
    selfie_segmentation = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
    #creating white background
    imgWhite = np.ones((img.shape[0],img.shape[1],3),np.uint8)*255
    # extract segmented mask
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = selfie_segmentation.process(img)
    #condition to apply the mask
    condition = np.stack(
      (results.segmentation_mask,) * 3, axis=-1) > 0.4
    #merging croped img with the white background
    noBackground = np.where(condition, img, imgWhite)
    selfie_segmentation.close()
    return noBackground

def print_prob(predict, letters, debug_image):

    colours = [(0, 244, 127),
                (250, 176, 55),
                (223, 198, 106),
                (208, 157, 74),
                (78, 174, 107)]
    output_frame = debug_image.copy()
    for num, prob in enumerate(predict):
        cv2.rectangle(output_frame, (0,60+num*40), (int(prob*100), 90+num*40), colours[num], -1)
        cv2.putText(output_frame, letters[num], (0, 85+num*40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2, cv2.LINE_AA)
    return output_frame


def about():
    st.write('Welcome to our drowiness detection system')
    st.markdown("""
     **About our app**
    - We are attempting to improve the communication all around.
    - Our app detects a hand using a live webcam and predicts the letter associated with the hand.""")

object_detection_page = "SignIntell"
about_page = "About SignIntell"

app_mode = st.sidebar.selectbox(
    "Choose the app mode",
    [
        object_detection_page,
        about_page
    ],)


st.subheader(app_mode)


@st.cache_data
def get_select_box_data():

    return list(" ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["del", "space"]

def result(top3,option):
    try:
        if top3[0]== option:
            st.success(f"Congratulations! You nailed it! you made {top3[0]}")
        else:
            st.write(f"Are you sure you're not doing {top3[1]} or {top3[2]}")
    except:
        pass

# pre-loading the model before calling the main function

if app_mode == object_detection_page:
    model = load_cloud_model()
    mp_model = load_mediapipe_model()
    df = get_select_box_data()

    #asking the user to select a letter to be predicted for comparison.
    option = st.selectbox('Select letter to practice', df)

    #if the selectbox returns a letter different than  " ", main function is called.
    if option != df[0]:
        img = Image.open(f"{st.secrets['EXAMPLES']}/{option}/{option}.jpg")
        st.image(img, caption='Try This!')
        app_sign_language_detection(model, mp_model)

if app_mode == about_page:
    about()
