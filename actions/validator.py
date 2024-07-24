from typing import Text, List, Any, Dict

from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
import re
import dateparser

patterns = [
            r'\d{1,2}\s*to\s*\d{1,2}',    # e.g., "20 to 22"
            r'\d{1,2}pm\s*to\s*\d{1,2}pm', # e.g., "3pm to 5pm"
            r'\d{1,2}am\s*to\s*\d{1,2}pm', 
            r'\d{1,2}pm\s*to\s*\d{1,2}am', 
            r'\d{1,2}am\s*to\s*\d{1,2}am', 
        ]

# Split the 'to' in it 
def split_before_and_after_to(input_string):
    # Find the index of the first occurrence of 'to' in the string
    index_of_to = input_string.find('to')

    # Check if 'to' exists in the string and is not the first or last character
    if index_of_to != -1 and index_of_to > 0 and index_of_to < len(input_string) - 1:
        # Split the string into two parts, before and after 'to'
        before_to = input_string[:index_of_to].strip()
        after_to = input_string[index_of_to + 2:].strip()
        return before_to, after_to
    else:
        # If 'to' is not present in the string or it's at the beginning/end, return None
        return None, None

class ValidateRoomForm(FormValidationAction):
    
    def name(self) -> Text:
        return "validate_room_form"

    def validate_times(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        normalized_message = slot_value.lower()
        
        check = True

        for pattern in patterns:
            if re.match(pattern, normalized_message, re.IGNORECASE):
                check = False
                return {"times": normalized_message}
        
        if check: 
            dispatcher.utter_message(text="Sorry, please try input checkin and checkout time in format: 07 to 14 or 7am to 2pm, remember to keep the 'to'.")
            return {"times": None}
    
    def validate_dates(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        normalized_message = slot_value.lower()
        
        var1, var2 = split_before_and_after_to(normalized_message)
        if var1 != None and var2 != None:
            if dateparser.parse(var1, settings={'PREFER_DATES_FROM': 'future'}) != None and dateparser.parse(var2, settings={'PREFER_DATES_FROM': 'future'}) != None:
                check = False
                for pattern in patterns:
                    if re.match(pattern, normalized_message, re.IGNORECASE):
                        dispatcher.utter_message(text="Please enter the date, not time.")
                        return {"dates": None}
                if check == False:
                    return {"dates": normalized_message}
        else:
            dispatcher.utter_message(text="Sorry, please try input dates in format: Jan 25th to Feb 4th, remember to keep the 'to' between check in and checkout")
            return {"dates": None}
        