from flask import Flask, render_template, request , jsonify
import os
import tensorflow as tf
from tensorflow import keras
from keras.models import load_model
import numpy as np
from PIL import Image
import sys
import requests
import io
from io import BytesIO
import json
import pandas as pd
from string import digits
import re
import unicodedata
import keras_nlp
import numpy as np
import pandas as pd
from transformers import DistilBertTokenizer


# Load the model with custom objects
mobileNet_image_model = tf.saved_model.load("models/MobileNetV3")

efficientNet_image_model = tf.saved_model.load("models/EfficientNet")

distilBert_text_model=tf.saved_model.load('models/distilbert_classifier')

app = Flask(__name__)
app.config["IMAGE_UPLOADS"] = "static/Uploads/"

@app.route("/")
def home():
    return render_template("helloWorld.html")

@app.route("/upload-image", methods=["","POST"])
def upload_image():
    if request.method == "POST":
        if "image" in request.files:
            image = request.files["image"]
            image.save(os.path.join(app.config["IMAGE_UPLOADS"], image.filename))
            filename = os.path.join(app.config["IMAGE_UPLOADS"], image.filename)
            predict_image = tf.keras.preprocessing.image.load_img(filename, target_size=(224, 224))
            predict_image = tf.keras.preprocessing.image.img_to_array(predict_image)
            predict_image = tf.expand_dims(predict_image, axis=0)
            prediction=mobileNet_image_model.signatures["serving_default"](predict_image)
            # input_tensor = tf.convert_to_tensor(eff_input, dtype=tf.float32)
            # Extracting the numpy array from the tensor
            non_violence,violence=prediction['dense'].numpy()[0]
            if non_violence<violence:
                prediction="Violence"
            else:
                prediction="Non-Violence"
            return render_template("upload_image.html", uploaded_image=filename, model_prediction=prediction )
    return render_template("upload_image.html")

@app.route('/process-image', methods=["POST"])
def process_image():
 if request.method == "POST":
    if "image" in request.files:
        image = request.files["image"]
        image.save(os.path.join(app.config["IMAGE_UPLOADS"], image.filename))
        filename = os.path.join(app.config["IMAGE_UPLOADS"], image.filename)
        predict_image = tf.keras.preprocessing.image.load_img(filename, target_size=(224, 224))
        predict_image = tf.keras.preprocessing.image.img_to_array(predict_image)
        predict_image = tf.expand_dims(predict_image, axis=0)
        prediction=mobileNet_image_model.predict(predict_image)
        if prediction[0][0]<prediction[0][1]:
            prediction="Violence"
        else:
            prediction="Non-Violence"

        return jsonify({'msg': 'success', 'prediction': [prediction]})
    return jsonify({'Error': 'BackendError'})

@app.route('/test', methods=["POST"])
def test():
    if request.method == "POST":
         if "image" in request.files:
             return jsonify({'msg': 'Bravo'})
         return jsonify({'msg': 'Bad'})


@app.route('/upload-urls',methods=["POST"])
def getImagesList():
    if request.method =="POST":
        if "images" in request.form:
            images=request.form['images']
            # img=json.loads(images)
            images=images.split(',')
            # return jsonify({'msg': 'success', 'images-recived':images})
            predictions={}
            multi_class_predictions={}
            for image in images:
                if image=="":
                    continue
                response = requests.get(image)
                img = Image.open(io.BytesIO(response.content)).resize((224,224)).convert('RGB')
                # img.save(os.path.join(app.config["IMAGE_UPLOADS"], img.filename))
                # filename = os.path.join(app.config["IMAGE_UPLOADS"], img.filename)
                # predict_image = tf.keras.preprocessing.image.load_img(io.BytesIO(response.content), target_size=(224, 224))
                predict_image = tf.keras.preprocessing.image.img_to_array(img)
                predict_image = tf.expand_dims(predict_image, axis=0)

                prediction=mobileNet_image_model.signatures["serving_default"](predict_image)
                eff_input=tf.keras.applications.efficientnet_v2.preprocess_input(predict_image)
               # input_tensor = tf.convert_to_tensor(eff_input, dtype=tf.float32)
                predic = efficientNet_image_model.signatures["serving_default"](eff_input)
                # Extracting the numpy array from the tensor
                non_violence,violence=prediction['dense'].numpy()[0]
                prediction_array = predic['output_0'].numpy()

                # Assigning each prediction to a separate variable
                accident, damaged_buildings, fire, normal = prediction_array[0]
                predictions_dict={"fire":fire,"accident":accident,'normal':normal,"damaged_buildings":damaged_buildings}
                # print(prediction)
                if non_violence<violence:
                    prediction="Violence"
                else:
                    prediction="Non-Violence"
                predictions[image]=prediction
                # print("prediction DEC:")
                # print(predictions_dict)
                # print(max(predictions_dict,key=predictions_dict.get))
                multi_class_predictions[image]=max(predictions_dict,key=predictions_dict.get)
            return jsonify({'msg': 'success', 'prediction': predictions,'mulit-class-prediction':multi_class_predictions})
        return jsonify({"BackendError":"Images not sent"})
    return jsonify({"BackendError": "Error in request"})

@app.route('/upload-text',methods=['POST'])
def getStringsList():
    print("GetStringListCalled")
    if request.method =="POST":
        if 'textData' in request.files:
            print("Call .files instead")
            return jsonify( {"Text Res":"call .files"})
        if 'textData' in request.form:
            textData=request.form['textData']
            textList=textData.split(",")
            text_prediction_dict={}
            for text in textList:
                text=pipelineText(text)
                print('==============================')
                print(text)
                padding_mask,token_ids=preprocess_text_list([text])
                print('==============================')
                predictions=distilBert_text_model.signatures["serving_default"](padding_mask=padding_mask,
                                                                                token_ids=tf.constant(token_ids))
                print(predictions)
                non_toxic,toxic=predictions['output_0'].numpy()[0]
                if non_toxic>toxic:
                    print("Non Toxic")
                    text_prediction_dict[text]='Non Toxic'
                else:
                    print("Toxic")
                    text_prediction_dict[text]='Toxic'
               
            return jsonify( {"TextPrediction":text_prediction_dict})
        return jsonify({"Error":"No data recived"})
    return jsonify({"Error ":"Wrong request"})

def pipelineText(text):
    slang= pd.read_csv('data/slang.csv',index_col=False)
    slang.set_index('acronym',drop=True,inplace=True)
    slang.drop('Unnamed: 0',axis=1, inplace=True)
    slang=slang.to_dict()
    inner_dict=slang['expansion']
    slang = {acronym: meaning for acronym, meaning in inner_dict.items()}
    text= remove_url(text)
    text= remove_days_months(text)
    text= remove_unicode_variations(text)
    text= remove_mentions(text)
    text= remove_hashtags(text)
    text= remove_special_characters(text)
    text= remove_redundant_characters_in_row(text)
    text= replace_acronyms_with_meanings(text,slang)
    text= remove_numbers(text)
    text= text.lower()
    return text
def replace_acronyms_with_meanings(text, acronym_dict):
    def replace_acronym(match):
        acronym = match.group(0)
        meaning = acronym_dict.get(acronym.lower(), acronym)
        return meaning

    pattern = r'\b[A-Z]{2,}\b'
    if isinstance(text, str):
        updated_text = re.sub(pattern, replace_acronym, text, flags=re.IGNORECASE)
        return updated_text
def remove_redundant_characters_in_row(row):
    if isinstance(row, str):
        words = row.split()
        cleaned_words = []
        for word in words:
            cleaned_word = ""
            prev_char = None
            count = 0

            for char in word:
                if char == prev_char:
                    count += 1
                    if count <= 2:
                        cleaned_word += char
                else:
                    cleaned_word += char
                    count = 1
                prev_char = char

            cleaned_words.append(cleaned_word)

        return " ".join(cleaned_words)
def remove_unicode_variations(input_string):
    if isinstance(input_string, str):
        normalized_string = unicodedata.normalize('NFKD', input_string)
        ascii_string = normalized_string.encode('ascii', 'ignore').decode('utf-8')
        return ascii_string
def remove_numbers(text):
    if isinstance(text, str):
        rem = str.maketrans('', '', digits)
        res = text.translate(rem)
        return res
def remove_special_characters(text):
    if isinstance(text, str):
        special_characters = r'[!@#$%*&()-+\n,.?/:;{}\'"><=`-]'
        pattern = re.compile(special_characters)
        return pattern.sub('', text)
def remove_url(text):
    if isinstance(text, str):
        url_pattern = re.compile(r'https?://\S+|www\.\S+')
        text=url_pattern.sub('', text)
    return text
def remove_days_months(text):
    if isinstance(text, str):
        day_names_pattern = r'\b(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\b'
        day_names = r'\b(?:mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b'
        month_names_pattern = r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b'
        month_names = r'\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b'
        combined_pattern = f'{day_names_pattern}|{month_names_pattern}|{day_names}|{month_names}'
        result = re.sub(combined_pattern, '', text)
        return result
def remove_hashtags(text):
    if isinstance(text, str):
        forms = [r'#\w+',  # form1(# followed by letters whether small or capital and/or numbers)
                 r'#([A-Z][a-z]+)([A-Z][a-z]+)'
                 # form2(# followed by capital letter,set of small letters , another capital letters and set of small letters -> part the 2 words)
                 ]
        all_forms = '|'.join(forms)
        pattern = re.compile(all_forms)
        return pattern.sub('', text)
    return text
def remove_mentions(text):

    if isinstance(text, str):
        forms = [r'@[A-Za-z0-9]+',  # form1
                 r'@[A-Za-z0-9]+/[A-Za-z0-9]+',  # form2
                 r'@[A-Za-z0-9]+[^\w\s]',  # form3
                 r'@[A-Za-z0-9]+:\s?'  # form4
                 ]
        all_forms = '|'.join(forms)
        pattern = re.compile(all_forms)
        text = pattern.sub('', text)
    return text
def preprocess_text_list(text_list):
    # Initialize the DistilBERT tokenizer
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    tokenized_texts = tokenizer(text_list, padding=True, truncation=True, return_tensors="tf")
    padding_mask = tokenized_texts["attention_mask"]
    token_ids = tokenized_texts["input_ids"]
    return padding_mask, token_ids
if __name__ == "__main__":
    app.run(debug=True)
