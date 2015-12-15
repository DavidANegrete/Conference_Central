#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)' 

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb


class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# - - - - - - - - - - -  Profile Object - - - - - - - - - - - - - - - - - - - 
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# 
# Changed the following for a user objects profile using Conference Central API. 
# 
#Profile(ndb.Model):
#   added:
#       conferenceKeysToAttend      
#           - Keeps conference keys if they will be attended.
#       sessionWishList
#           - Keeps wish list keys if they will be attended.
#
# ProfileForm(message.Message):
#   added:
#       conferenceKeysToAttend + sessionWishList
#           - Added to copy from the ndb object and display.
#                  
class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName             = ndb.StringProperty()
    mainEmail               = ndb.StringProperty()
    teeShirtSize            = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend  = ndb.StringProperty(repeated=True)
    sessionWishList         = ndb.StringProperty(repeated=True)
    

class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName             = messages.StringField(1)
    TeeShirtSize            = messages.EnumField('TeeShirtSize', 2)


class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName             = messages.StringField(1)
    mainEmail               = messages.StringField(2)
    teeShirtSize            = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend  = messages.StringField(4, repeated=True)
    sessionWishList         = messages.StringField(5, repeated=True)
    

class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# - - - - - - - - - - -  Conference Object  - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
#
class Conference(ndb.Model):
    """Conference -- Conference object"""
    name                    = ndb.StringProperty(required=True)
    description             = ndb.StringProperty()
    organizerUserId         = ndb.StringProperty()
    topics                  = ndb.StringProperty(repeated=True)
    city                    = ndb.StringProperty()
    startDate               = ndb.DateProperty()
    month                   = ndb.IntegerProperty()
    endDate                 = ndb.DateProperty()
    maxAttendees            = ndb.IntegerProperty()
    seatsAvailable          = ndb.IntegerProperty()


class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name                    = messages.StringField(1)
    description             = messages.StringField(2)
    organizerUserId         = messages.StringField(3)
    topics                  = messages.StringField(4, repeated=True)
    city                    = messages.StringField(5)
    startDate               = messages.StringField(6) #DateTimeField()
    month                   = messages.IntegerField(7)
    maxAttendees            = messages.IntegerField(8)
    seatsAvailable          = messages.IntegerField(9)
    endDate                 = messages.StringField(10) #DateTimeField()
    websafeKey              = messages.StringField(11)
    organizerDisplayName    = messages.StringField(12)


class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)


# - - - - - - - - - - -  Query forms - - - - - - - - - - - - - - - - - - - - 
class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field                   = messages.StringField(1)
    operator                = messages.StringField(2)
    value                   = messages.StringField(3)


class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)

# used when users register to a Conference
class BooleanMessage(messages.Message):

    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# - - - - - - - - - - -  Session Object - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  
# 
# The Session ndb.model stores a Session Object this object has a 'has-a'
# relationship with the Conference object. This is an extension of the 
# Conference  object. It has six string field properties, two are
# required, one integer.
# 
# StringProperty:
#   REQUIRED:
#       (name)
#           - Used to save a sessions name.
#
#       (parentKey)
#           - Represents the parent Conference key, creates the has-a relationship between
#             a session and its parent Conference.     
#
#   OPTIONAL:
#       (highlights)
#           - Saves the description of the things that make a session special.
#
#       (speakerID) 
#           - Saves the speaker key.
#
#       (typeOfSession)
#           default value: 'GENERAL'
#           - Saves type of session (ex. workshop, tutorial). By default
#             it's set to 'GENERAL' which represents the default option in
#             the SessionType(enumeration) object.
#
# IntegerProperty:
#   OPTIONAL:
#       (duration)
#           - Save the amount of time in minutes a session will take.
#
# DateProperty:
#   OPTIONAL:
#       (date)
#           - Stores the date a session will be on.
#   
# TimeProperty:
#   OPTIONAL:
#       (startTime)
#           - Will be used to represent the sessions start time in 24 hr notation.                                 
#
class Session(ndb.Model):
    """Session -- Session object"""
    name                    = ndb.StringProperty(required=True)
    highlights              = ndb.StringProperty()
    speakerID               = ndb.StringProperty(repeated=True)
    duration                = ndb.IntegerProperty()
    typeOfSession           = ndb.StringProperty(default='GENERAL')
    date                    = ndb.DateProperty()
    month                   = ndb.IntegerProperty()  
    startTime               = ndb.TimeProperty()
    parentKey               = ndb.StringProperty(required=True)


class SessionForm(messages.Message):
    """SessionForm -- Session outbound form message"""
    name                    = messages.StringField(1)
    highlights              = messages.StringField(2)
    speakerID               = messages.StringField(3, repeated=True)
    duration                = messages.IntegerField(4)
    typeOfSession           = messages.EnumField('SessionType',5)
    date                    = messages.StringField(6) #DateTimeField()
    startTime               = messages.StringField(7) #DateTimeField()
    parentKey               = messages.StringField(8) 


class SessionForms(messages.Message):
    """SessionForms -- multiple Session outbound form messages"""
    items = messages.MessageField(SessionForm, 1, repeated=True)

# SessionType enum holder of the values available
class SessionType(messages.Enum):
    """SessionType -- session type enumeration value"""
    GENERAL                 = 1
    WORKSHOP                = 2
    TUTORIAL                = 3
    SEMINAR                 = 4
    FORUM                   = 5


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
# - - - - - - - - - - -  Speaker Object - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# The Speaker ndb.model stores a Speaker Object it is a sole entity and can be 
# related to one or many Session Objects. The Speaker ndb.model has 5 string 
# field properties two are required.
# 
# StringProperty:
#   REQUIRED:
#       (name)
#           - Represents the name of a speaker.
#   OPTIONAL:
#       (bio)
#           - Is an overview of the speaker. 
#       (company)
#           - Holds one or many companies a speaker works or has worked for.
#       (projects)
#           - A list of projects that speaker has accomplished
class Speaker(ndb.Model):
    """Speaker -- Speaker object"""
    name      = ndb.StringProperty(required=True)
    bio       = ndb.StringProperty()
    company   = ndb.StringProperty(repeated=True)
    projects  = ndb.StringProperty(repeated=True)


class SpeakerForm(messages.Message):
    """SpeakerForm -- Speaker outbound form message"""
    name       = messages.StringField(1)
    bio        = messages.StringField(2)
    company    = messages.StringField(3, repeated=True)
    projects   = messages.StringField(4, repeated=True)


class SpeakerForms(messages.Message):
    """SpeakerForms -- Multiple Speaker outbound form message"""
    items = messages.MessageField(SpeakerForm, 1, repeated=True)
