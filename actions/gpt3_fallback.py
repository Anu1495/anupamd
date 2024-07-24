import openai
import os
import time
import json
import datetime
import logging
import requests
import base64
from json.decoder import JSONDecodeError
from dotenv import load_dotenv
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Any, Text, Dict, List
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain import PromptTemplate
# from boto3 import resource
# from boto3.dynamodb.conditions import Attr, Key
import pyodbc 

# frontend_db = resource('dynamodb',
#     aws_access_key_id="AKIASELV2RFJHLDR54FJ",
#     aws_secret_access_key="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", region_name='eu-west-2').Table('Rasa-Backend-Conversations')
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

class ActionGPT3Fallback(Action):
    def utterAndTrack(self, message, dispatcher, sender_id):
        dispatcher.utter_message(text=message)
        self.sender2messageList[sender_id].append({"role":"assistant","content":message})
        # self.db_insert(message,sender_id=sender_id, role="assistant")
        self.responseMadeDict[sender_id] = True

    def runClassifier(self, tracker):
        sender_id = tracker.sender_id
        latest_message = tracker.latest_message['text']
        if sender_id not in self.sender2messageList:
            self.sender2messageList[sender_id] = []
            self.sender2messageList[sender_id].append({"role":"system","content":self.classify_prompt()})
        self.sender2messageList[sender_id].append({"role":"user","content":latest_message})
        # self.db_insert(latest_message, role='user', sender_id=tracker.sender_id)
    
        
        response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=self.sender2messageList[sender_id]
        )
        try:
            self.sender2messageList[sender_id].append({"role":"assistant","content":response['choices'][0]['message']['content']})
            response_content = json.loads(response['choices'][0]['message']['content'])
        except JSONDecodeError:
            self.sender2messageList[sender_id].append({"role":"system","content":'Output a JSON dictionary in the format: {"intent":INTENT, "start_date":START_DATE, "end_date":END_DATE, "start_time":START_TIME, "end_time":END_TIME}. If a variable is not given leave it blank. Give just the JSON dictionary as the output and no explanation.'})
            response_content = {"intent":"ERROR"}
        self.logger.info(response_content)
        return response_content
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        connection_string = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=flexisql.uksouth.cloudapp.azure.com,1433;DATABASE=flexibookings_v4;TrustServerCertificate=yes;UID=dhruv;PWD=R!LWg$^hVOTy"
        self.cnxn = pyodbc.connect(connection_string)
        self.cursor = self.cnxn.cursor()
        self.responseMadeDict = dict()
        self.metadata = dict()
        self.logger.setLevel(logging.INFO)
        self.sender2messageList = dict()
        self.sender2booking = dict()
        self.classify_prompt = lambda : "Ignore previous system instructions.\n" + \
                        "Your task is to classify a piece of text for a hotel management system and output a JSON dictionary.\n"+ \
                        "You will classify the text into one of four intents . The intents are ['ADD_OFFER', 'REMOVE_TAGS', 'MISCELLANEOUS','HELLO'].\n"+ \
                        "The intent field is mandatory and cannot be left blank. \n" + \
                        "If the text wants to add a promo code or a discount then the intent is 'ADD_OFFER'\n" + \
                        'Output a JSON dictionary in the format: {"intent":INTENT}.\n'
                        # "If the text contains them, you will also extract the booking start date and booking end date, and the checking-in date and checking-out date. The dates are in the format DD/MM/YYYY.\n" + \
                        # "Use the full conversation to build the output." + \
                        # "Today is "+time.strftime("%A")+" and today's date is "+time.strftime("%d/%m/%Y")+" in DD/MM/YYYY format. If the text does not give the year, infer it as the current year.\n" + \
        self.promo_prompt = lambda : "Ignore previous system instructions.\n" + \
                                    "The user will now provide details about changing the settings for a promo code, you will have to extract the information they provide and output a JSON dictionary.\n" + \
                                    "If the text asks you to generate a description, then generate a sample description for an offer using the details in the past JSON dictionary and add the description to the current JSON output.\n"+ \
                                    "If the text contains them, you will extract data relevant to its field." + \
                                    "Use the full conversation to build the output." + \
                                    "Today is "+time.strftime("%A")+" and today's date is "+time.strftime("%d/%m/%Y")+" in DD/MM/YYYY format. If the text does not give the year, infer it as the current year.\n" + \
                                    "Discount is a float between 0 and 100. Do not include the percent sign in the output JSON for discount.\n" + \
                                    'Output a JSON dictionary in the format {"title":TITLE,"booking_from":BOOKING_FROM_DATE, "booking_until":BOOKING_TIL_DATE, "checking_in":CHECKING_IN_DATE, "checking_out":CHECKING_OUT_DATE,"promo_code":PROMO_CODE,"description":DESCRIPTION,"discount":DISCOUNT}.\n'
                                    # 'The fields are: ["title","booking_from","booking_until", "checking_in_date","checking_out_date","promo_code","description","discount"]'
        self.confirm_prompt = lambda : "Your task now is to classify a piece of text and output a JSON dictionary.\n" + \
                                        "You will classify the text into one of three intents. The intents are ['CONFIRM','CHANGE','RESET'].\n" + \
                                        'Output a JSON dictionary in the format: {"intent":INTENT}.\n'
        # self.retriever_chatbot = RetrievalQA.from_chain_type(
        #                             llm=ChatOpenAI(
        #                                 openai_api_key=os.getenv("OPENAI_API_KEY"),
        #                                 temperature=0, model_name="gpt-4", max_tokens=1800, verbose=True
        #                             ),
        #                             chain_type="stuff", 
        #                             retriever=FAISS.load_local("./faiss_docs", OpenAIEmbeddings())
        #                                 .as_retriever(search_type="similarity", search_kwargs={"k":10}), 
        #                             )
        
        super().__init__()
    def sendapirequest(self,weburl): 
        response = requests.get(weburl)
        data = response.json()
        return data 
    def ratesjson(self, apiresponse):
        data = apiresponse
        # Function to find the cheapest rate in a list of rates
        def get_cheapest_rate(rates):
            return min(rates, key=lambda x: x["Price"])
        roomlist = []
        ratelist = []
        photolist = []
        # Loop through each room and find the cheapest rate
        for room in data:
            room_name = room["RoomName"]
            roomlist.append(f"Room: {room_name}")
            rates = room["Rates"]
            cheapest_rate = get_cheapest_rate(rates)
            ratelist.append(f"Cheapest Rate: {cheapest_rate['Price']} {cheapest_rate['Currency']}")
            self.logger.info(f"Room: {room_name}")
            self.logger.info(f"Cheapest Rate: {cheapest_rate['Price']} {cheapest_rate['Currency']}\n")
            
            photo = room["Photos"][0]["Medium"]
            photolist.append(photo)
        
        self.logger.info(roomlist)
        self.logger.info(ratelist)
        return roomlist, ratelist, photolist
    # def updateBookingRoomDetails(self, classifiedResponse,sender_id):
    #         missing = []
    #         if 'start_date' not in classifiedResponse or classifiedResponse['start_date'] == '':
    #             missing.append("Check-in date")
        
    #         if 'end_date' not in classifiedResponse or classifiedResponse['end_date'] == '':
    #             missing.append("Check-out date")
        
    #         if 'start_time' not in classifiedResponse or classifiedResponse['start_time'] == '':
    #             missing.append("Check-in time")
        
    #         if 'end_time' not in classifiedResponse or classifiedResponse['end_time'] == '':
    #             missing.append("Check-out time")
    #         return missing

    # def bookRoom(self, classifiedResponse, tracker, dispatcher):
    #     missing = self.updateBookingRoomDetails(classifiedResponse, tracker.sender_id)
    #     if missing != []:
    #         detail_message = "Please provide the following information to book a room: " + ", ".join(missing)
    #         self.utterAndTrack(detail_message, sender_id=tracker.sender_id, dispatcher=dispatcher)
    #     else:            
    #         checkintime = datetime.datetime.strptime(classifiedResponse['start_time'], '%H:%M').strftime('%H') 
    #         checkouttime = datetime.datetime.strptime(classifiedResponse['end_time'], '%H:%M').strftime('%H') 
    #         checkindate = datetime.datetime.strptime(classifiedResponse['start_date'], '%d/%m/%Y').strftime('%Y-%m-%d') 
    #         checkoutdate = datetime.datetime.strptime(classifiedResponse['end_date'], '%d/%m/%Y').strftime('%Y-%m-%d') 
    #         weburl = f"https://www.mercurehydepark.com/book/?rates=&checkin={checkindate}&checkintime={checkintime}&checkout={checkoutdate}&checkouttime={checkouttime}"
    #         apiurl = f"https://flexibookingsapi.azurewebsites.net/api/Search/HotelRates?Id=47&checkInDate={checkindate}&checkOutDate={checkoutdate}&checkInTime={checkintime}&checkOutTime={checkouttime}"
    #         self.utterAndTrack(f"Here is a link to book these rooms: {weburl}\n", sender_id=tracker.sender_id, dispatcher=dispatcher)
    #         self.logger.info(f"API URL: {apiurl}")
    #         result = ""
    #         try:
    #             data = self.sendapirequest(apiurl)
    #             rooms, rates, photos = self.ratesjson(data)
    #             for room, rate in zip(rooms, rates):
    #                 result += f"{room}\n{rate}\n"
    #         except Exception:
    #             self.logger.error(f"Unable to read API output from URL {apiurl}:\n{data}")
    #         if result != "":
    #             self.utterAndTrack(result, sender_id=tracker.sender_id, dispatcher=dispatcher)
    def convertDate(self, date):
        return datetime.datetime.strptime(date, '%d/%m/%Y').strftime('%m/%d/%Y') 
    def updatePromoCodeDetails(self, classifiedResponse,sender_id):
            missing = []
            optional_missing = []
            if 'title' in classifiedResponse and classifiedResponse['title'] != '':
                self.metadata[sender_id]['data']['title'] = classifiedResponse['title']
            elif 'title' not in self.metadata[sender_id]['data']:
                missing.append("Title of offer")
                
            if 'booking_from' in classifiedResponse and classifiedResponse['booking_from'] != '':
                self.metadata[sender_id]['data']['booking_from'] = self.convertDate(classifiedResponse['booking_from'])
            elif 'booking_from' not in self.metadata[sender_id]['data']:
                missing.append("Booking-from date")
                
            if 'booking_until' in classifiedResponse and classifiedResponse['booking_until'] != '':
                self.metadata[sender_id]['data']['booking_until'] = self.convertDate(classifiedResponse['booking_until'])
            elif 'booking_until' not in self.metadata[sender_id]['data']:
                missing.append("Booking-until date")
                
            if 'checking_in' in classifiedResponse and classifiedResponse['checking_in'] != '':
                self.metadata[sender_id]['data']['checking_in'] = self.convertDate(classifiedResponse['checking_in'])
            elif 'checking_in' not in self.metadata[sender_id]['data']:
                missing.append("Checking-in date")
                
            if 'checking_out' in classifiedResponse and classifiedResponse['checking_out'] != '':
                self.metadata[sender_id]['data']['checking_out'] = self.convertDate(classifiedResponse['checking_out'])
            elif 'checking_out' not in self.metadata[sender_id]['data']:
                missing.append("Checking-out date")
                
            if 'description' in classifiedResponse and classifiedResponse['description'] != '':
                self.metadata[sender_id]['data']['description'] = classifiedResponse['description']
            elif 'description' not in self.metadata[sender_id]['data']:
                missing.append("Description")
                
            if 'discount' in classifiedResponse and classifiedResponse['discount'] != '':
                self.metadata[sender_id]['data']['discount'] = classifiedResponse['discount']
            elif 'discount' not in self.metadata[sender_id]['data']:
                missing.append("Discount")
                
            if 'promo_code' in classifiedResponse and classifiedResponse['promo_code'] != '':
                self.metadata[sender_id]['data']['promo_code'] = classifiedResponse['promo_code']
            elif 'promo_code' not in self.metadata[sender_id]['data']:
                optional_missing.append("Promo Code")
                
            return missing, optional_missing
        
    def askOfferConfirmation(self, tracker, dispatcher):
        message = "Received all required information.\nThe offer creation update will use the following information:\n\n"
        for key,value in self.metadata[tracker.sender_id]['data'].items():
            message += f"{key} : {value}\n\n"
        message += "Type in:\n'CONFIRM' to confirm the update.\n'CHANGE' to modify the update.\n'RESET' to start over."
        self.utterAndTrack(message, sender_id=tracker.sender_id, dispatcher=dispatcher)
        self.messageSystem(message=self.confirm_prompt(), sender_id=tracker.sender_id)
    def messageSystem(self, message, sender_id):
        self.sender2messageList[sender_id].append({"role":"system","content":message})

    def addPromoCode(self, classifiedResponse, tracker, dispatcher):
        missing, optional_missing = self.updatePromoCodeDetails(classifiedResponse, tracker.sender_id)
        self.messageSystem(message=self.promo_prompt(),sender_id=tracker.sender_id)
        self.logger.info(f"missing list: {missing}")
        if missing != []:
            detail_message = "The following information is required to add an offer: " + ", ".join(missing)
            if optional_missing != []:
                detail_message += "\n\nThe following information is optional to add to an offer: " + "\n".join(optional_missing)
            
            self.utterAndTrack(detail_message, sender_id=tracker.sender_id, dispatcher=dispatcher)
        else:
            # checkindate = datetime.datetime.strptime(classifiedResponse['checking_in'], '%d/%m/%Y').strftime('%Y-%m-%d') 
            # checkoutdate = datetime.datetime.strptime(classifiedResponse['checking_out'], '%d/%m/%Y').strftime('%Y-%m-%d') 
            # bookingfromdate = datetime.datetime.strptime(classifiedResponse['booking_from'], '%d/%m/%Y').strftime('%Y-%m-%d') 
            # bookinguntildate = datetime.datetime.strptime(classifiedResponse['booking_until'], '%d/%m/%Y').strftime('%Y-%m-%d') 
            
            self.askOfferConfirmation(tracker, dispatcher)
            

    def sql_update(self,sender_id,dispatcher):
        if self.metadata[sender_id]['intent'] == "ADD_OFFER":
            sql = """
                {CALL uspCreateOfferV2 (@Title=?, @BookingsFrom=?,@BookingsUntil=?,@Description=?,@Discount=?,@PromoCode=?,@StayFrom=?,@StayUntil=?,@Days=?)}
                """
            fields = ['title','booking_from','booking_until','description','discount', 'promo_code', 'checking_in', 'checking_out', 255]
            parameters = [self.metadata[sender_id]['data'].get(f,None) for f in fields]
            try:
                self.cursor.execute(sql,parameters) 
                id = self.cursor.fetchone()[0]
                self.cnxn.commit()
                message = "Successfully made SQL update!"
                self.utterAndTrack(message, sender_id=sender_id, dispatcher=dispatcher)
            except pyodbc.Error as ex:
                message = "Failed to make the SQL update. Please retry the query!"
                self.utterAndTrack(message, sender_id=sender_id, dispatcher=dispatcher)
            finally:
                self.messageSystem(self.classify_prompt(), sender_id=sender_id)
                self.utterAndTrack("Hi, I can currently add promo codes (other tasks are under development). What task do you want me to do?", sender_id=sender_id, dispatcher=dispatcher)
                self.metadata[sender_id] = {"intent":None,
                                                "data": dict()}


    # def db_insert(self, msg, sender_id, role):
    #     # encoded_msg = base64.b64encode(msg)
    #     frontend_db.put_item(
    #         Item={
    #             "user_id" : sender_id,
    #             "message" : msg,
    #             "role": role,
    #             "timestamp": datetime.datetime.utcnow().isoformat()
    #             }
    #     )
    def name(self) -> str:
        return "action_gpt3_fallback"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        self.responseMadeDict[tracker.sender_id] = False
        classifiedResponse = self.runClassifier(tracker)
        if tracker.sender_id not in self.metadata:
            self.metadata[tracker.sender_id] = {"intent":None,
                                                "data": dict()}
        if self.metadata[tracker.sender_id]['intent'] == None:
            if classifiedResponse['intent'] == "ERROR":
                self.utterAndTrack("Sorry, I couldn't process that correctly. Can you please try again?", sender_id=tracker.sender_id, dispatcher=dispatcher)
            # elif classifiedResponse['intent'] == "MISCELLANEOUS" or classifiedResponse['intent'] == "":
            #     self.utterAndTrack("As an AI chatbot for Mercure's Paddington, I only have a limited amount of information. If you think this information will be helpful, type in 'yes' and we will update our FAQ list!", sender_id=tracker.sender_id, dispatcher=dispatcher)
            elif classifiedResponse['intent'] == "HELLO":
                msg = "Hi, I can currently add promo codes (other tasks are under development). What task do you want me to do?"
                dispatcher.utter_message(text=msg)
                # self.db_insert(msg, role='assistant', sender_id=tracker.sender_id)
                self.responseMadeDict[tracker.sender_id] = True
            elif classifiedResponse['intent'] == "REQUEST_FAQ" or classifiedResponse['intent'] == "MISCELLANEOUS" or classifiedResponse['intent'] == "":
                request = tracker.latest_message['text']
                template = """
                Answer the Question: Answer in the same language as the question is asked. {query}
                """

                prompt = PromptTemplate(
                    input_variables=["query"],
                    template=template,
                )
                
                gptresponse = self.retriever_chatbot.run(prompt.format(query=request))        
                self.utterAndTrack(gptresponse, sender_id=tracker.sender_id, dispatcher=dispatcher)
            elif self.metadata[tracker.sender_id]['intent'] == "ADD_OFFER" or classifiedResponse['intent'] == "ADD_OFFER":
                self.metadata[tracker.sender_id]['intent'] = classifiedResponse['intent']
                self.addPromoCode(classifiedResponse, tracker, dispatcher)
        elif self.metadata[tracker.sender_id]['intent'] == 'ADD_OFFER':
            if 'intent' in classifiedResponse:
                if classifiedResponse['intent'] == "CONFIRM":
                    self.sql_update(tracker.sender_id, dispatcher)
                elif classifiedResponse['intent'] == "CHANGE":
                    if self.metadata[tracker.sender_id]['intent'] == 'ADD_OFFER':
                        self.messageSystem(message=self.promo_prompt(), sender_id=tracker.sender_id)
                        self.utterAndTrack(message="What change do you want to make?", sender_id=tracker.sender_id,dispatcher=dispatcher)
                    else:
                        self.utterAndTrack("Operation cancelled. You will have to restart the entire process.", sender_id=tracker.sender_id,dispatcher=dispatcher)
                        self.messageSystem(message=self.classify_prompt(), sender_id=tracker.sender_id)
                        self.utterAndTrack("Hi, I can currently add promo codes (other tasks are under development). What task do you want me to do?", sender_id=tracker.sender_id,dispatcher=dispatcher)
                        self.metadata[tracker.sender_id]['data'] = dict()
                        self.metadata[tracker.sender_id]['intent'] = None
                elif classifiedResponse['intent'] == "RESET":
                    self.messageSystem(message=self.classify_prompt(),sender_id=tracker.sender_id)
                    self.utterAndTrack("Operation cancelled.\nHi, I can currently add promo codes (other tasks are under development). What task do you want me to do?", sender_id=tracker.sender_id,dispatcher=dispatcher)
                    self.metadata[tracker.sender_id]['data'] = dict()
                    self.metadata[tracker.sender_id]['intent'] = None
            elif self.metadata[tracker.sender_id]['intent'] == "ADD_OFFER":
                self.addPromoCode(classifiedResponse, tracker, dispatcher)

        # elif classifiedResponse['intent'] == "BOOK_ROOM":
        #     self.bookRoom(classifiedResponse, tracker, dispatcher)
        
        if not self.responseMadeDict[tracker.sender_id]:
            msg = "I'm sorry I could not quite understand that. Can you please retry your query?"
            dispatcher.utter_message(text=msg)
            # self.db_insert(msg, role='assistant', sender_id=tracker.sender_id)
            self.responseMadeDict[tracker.sender_id] = True

        return []
    
