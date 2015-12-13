#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.ext import ndb

from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import TeeShirtSize
#from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionType


from utils import getUserId
from utils import getUser
from utils import checkFieldValue
from utils import checkField
from utils import checkUsers
from utils import checkObj
from utils import getParentKey

from settings import WEB_CLIENT_ID

import logging

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID


# - - - FormField Constants/Default Values - - - - - - - - - - - - - - - - - - F

# Used to fill the Conference form if any fields are left blank.
CONFERENCE_DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

# Used to fill the Session form if any fields are left blank.
SESSION_DEFAULTS =  {'duration'      : 0,
                    'typeOfSession' : SessionType.GENERAL,}

# Used to fill the Conference query operands
OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }
FIELDS = {'CITY'          : 'city',
          'TOPIC'         : 'topics',
          'MONTH'         : 'month',
          'MAX_ATTENDEES' : 'maxAttendees',
          }


# - - - Resource Containers - - - - - - - - - - - - - - - - - - - - - - - - -
CONFERENCE_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm, websafeConferenceKey=messages.StringField(1))

CONFERENCE_GET_REQUEST =  endpoints.ResourceContainer(
    message_types.VoidMessage, websafeConferenceKey=messages.StringField(1))


SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm, websafeConferenceKey=messages.StringField(1))

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage, websafeConferenceKey=messages.StringField(1))

SESSION_GET_REQUEST_BY_TYPE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    typeOfSession = messages.StringField(2, required=True),
    websafeConferenceKey = messages.StringField(1))



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
@endpoints.api( name='conference',
                version='v1',
                allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
                scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Profile objects - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""

        user = getUser()
        
        user_id = getUserId(user)

        # Using the users retrieved email and an ndb.key is returned.
        p_key = ndb.Key(Profile, user_id)
        
        # p_key.get(), returns a users profile from DataStore.
        profile = p_key.get()

        # Create new Profile if not found.
        if not profile:
            # Profile object is created.
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifiable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)

# - - - EndPoints Methods (Profile) - - - - - - - - - - - - - - - - - - - - - 
    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Conference objects - - - - - - - - - - - - - - - - - - - - - - - - - 

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
           
        # Checking if the user if is signed if not an exception is raised
        # imported from utils.py
        user = getUser()
        
        # This method returns a user_id (email)
        user_id = getUserId(user)

        # Checking if the name field is filled or throwing an error.  
        # The checkFieldValue method checks if a field is filled or an Exception is raised. 
        # Passed to it is the request and the string value of the field.
        checkFieldValue(request.name)

        # Copying the ConferenceForm/ProtoRPC Message 
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # adding default values for those missing data & outbound Message
        for df in CONFERENCE_DEFAULTS:
            if data[df] in (None, []):
                data[df] = CONFERENCE_DEFAULTS[df]
                setattr(request, df, CONFERENCE_DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        # both for data model & outbound Message
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
            setattr(request, "seatsAvailable", data["maxAttendees"])

        # make Profile Key from user ID
        p_key = ndb.Key(Profile, user_id)
        
        # allocate new Conference ID with Profile key as parent
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        
        # make Conference key from ID
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference & return (modified) ConferenceForm
        Conference(**data).put()

        return request

# - - - Endpoints Methods (Conference)  - - - - - - - - - - - - - - - - - - - 
    
    # post request to create a new Conference
    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    # Returns all conferences created
    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        
        # Using the get method to pass the correctly formated query 
        conferences = self._getQuery(request)

        logging.debug("_______DEBUG START________________")
        for o in conferences:
            logging.debug(o)
        logging.debug("_______DEBUG END________________")

         # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, "") \
            for conf in conferences]
        )

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
        path='getConferencesCreated',
        http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
         
        # Verifying the current user is authorized 
        # if so a user object is returned,
        # or an exception is raised if not authorized.
        user = getUser()

        # make profile key
        p_key = ndb.Key(Profile, getUserId(user))
        
        # create ancestor query for this user
        conferences = Conference.query(ancestor=p_key)
        
        # get the user profile and display name
        prof = p_key.get()
        displayName = getattr(prof, 'displayName')
        
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, displayName) for conf in conferences]
        )

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
        path='queryConferencesCreated',
        http_method='GET', name='queryConferencesCreated')
    def queryConferencesCreated(self, request):

        """Query conferences created by user."""
         
        q = Conference.query()
        q = q.filter(Conference.organizerUserId == "danegrete79@gmail.com")
        q = q.order(Conference.name)

        return ConferenceForms(
            items=[self._copyConferenceToForm(f, "") for f in q]
            )

    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q

    # This method checks the the supplied filters filters  information 
    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


# - - - Session objects - - - - - - - - - - - - - - - - - - - - - - - - - - - 
    def _copyConferenceSessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""
        s_form = SessionForm()
        for field in s_form.all_fields():
            if hasattr(session, field.name):
                
                # Convert date and startTime fields to strings
                if field.name == 'date' or field.name == 'startTime':
                    setattr(s_form, field.name, str(getattr(session, field.name)))
                
                # Convert to enumeration value type
                elif field.name == 'typeOfSession':
                    setattr(s_form, field.name, getattr(SessionType,
                                                    getattr(session, field.name)))
                # Just copy over the fields
                else:
                    setattr(s_form, field.name, getattr(session, field.name))
            
            # Convert DataStore keys in to URL compatible strings
            elif field.name == 'parentConfKey':
                setattr(s_form, field.name, session.key.urlsafe())
        s_form.check_initialized()
        return s_form

    def _createSessionObject(self, request):
        """Create a Session object, returning SessionForm/request."""
        
        # Verifying if the current user is authorized 
        # and a user object returned
        # or an Unauthorized exception is raised.
        user = getUser()
        
        # Returns a users id (email)
        user_id = getUserId(user)

        # Verifying if the 'name' field is empty,
        # raising a Bad Request Exception if it is.
        # checkField accepts two variables
        # 1) the request
        # 2) the string equivalent of the name of a given field. 
        checkField(request.name, 'name')

        # Verifying if the 'parentKey' is empty,
        # raising a Bad Request Exception if it is.
        checkField(request.parentKey, 'parentKey')
        
        # Get an ndb key using the parent key
        # or a Bad Request Exception is raised.
        #_key = getParentKey(request.parentKey)
        try:
            _key = ndb.Key(urlsafe=request.parentKey)
        except Exception:
            raise endpoints.BadRequestException(
            'Key error. (Error 400)')
            
        # Get a Conference object from DataStore
        con_object = _key.get()

        # Verify that the current user created the Conference
        # or a Forbidden Exception is raised. 
        checkUsers(user_id, con_object)

        # Copy SessionForm ProtoRPC message and unpack it to a dictionary
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})

        # Validate the input and populate the dictionary
        # with default data, if values or missing
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]
                setattr(request, df, SESSION_DEFAULTS[df])
        
        # Converting the date info from strings to Date objects
        # setting the object month to the start dates month
        if data['date']:
            data['date'] = (datetime.strptime(
                            data['date'][:10], "%Y-%m-%d").date())
            data['month'] = data['date'].month
        else:
            data['month'] = con_object.month
        
        # Convert startTime from string to Time object
        if data['startTime']:
            data['startTime'] = (datetime.strptime(
                                 data['startTime'][:5], "%H:%M").time())
        
        # Convert typeOfSession to string
        if data['typeOfSession']:
            data['typeOfSession'] = str(data['typeOfSession'])
        
        # Create a session id for the Session, 
        # create the relationship with parent key.
        s_id  = Session.allocate_ids(size = 1, parent = _key)[0]
        
        # Create the session key
        s_key = ndb.Key(Session, s_id, parent = _key)
        
        # Fill the session key
        data['key'] = s_key
        
        # Store the created Session in the DataStore
        Session(**data).put()
        
        # Send an email to the organizer that the changes went through.
        #taskqueue.add(
         #   params = {
          #      'email'   : user.email(),
           #     'subject' : 'You Created a New Session for %s!' % con_object.name,
            #    'body'    : 'Here are the details for your session:',
             #   'info'    : repr(request)},
            #url    = '/tasks/send_confirmation_email')
        return request

# - - - Endpoints Methods (Session)  - - - - - - - - - - - - - - - - - - - 


    # post request to create a new Session
    @endpoints.method(SessionForm,
                    SessionForm,
                    path='conference',
                    http_method='POST',
                    name='createSession')
    def createConference(self, request):
        """Create new conference."""
        return self._createSessionObject(request)
 

    @endpoints.method(SESSION_GET_REQUEST,
                    SessionForms,
                    path        = 'sessions/{websafeConferenceKey}',
                    http_method = 'GET',
                    name        = 'getConferenceSessions')
    def getConferenceSessions(self, request):
        """Given a conference, return the sessions."""
        
        # Verifying if the current user is authorized 
        # and a user object returned
        # or an Unauthorized exception is raised.
        user = getUser()
        
        # Returning the user_id
        user_id = getUserId(user)

        # change the method get parentKey  
        try:
            _key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException(
                'The websafeConferenceKey given is invalid.')
        
        # Verify that the Conference exists
        conference = _key.get()

        # This method accepts two variables
        # 1) the object
        # 2) the string equivalent of the name of the object. 
        checkObj(conference, 'Conference')

        # Get the Sessions that are ancestors of the Conference
        sessions = Session.query(ancestor=_key)
        
        # Return a SessionForm for each Session
        return SessionForms(
            items = [self._copyConferenceSessionToForm(
                sess) for sess in sessions])


    # Given a Conference returns all session of a specified type.
    @endpoints.method(SESSION_GET_REQUEST_BY_TYPE,
                SessionForms,
                path        = 'getConferenceSessionsByType/'
                '{websafeConferenceKey}/{typeOfSession}',
                http_method = 'GET',
                name        = 'getConferenceSessionsByType')
    def getConferenceSessionByType(self, request):
        '''Given a conference key return sessions of a specified type'''

        # Checking if the user if is signed if not an exception is raised
        # imported from utils.py
        user = getUser()

        # First query for a session with specified key. 
        session = Session.query(
            ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))

        # Second query for remaining Sessions by the type specified
        session = session.filter(
            Session.typeOfSession == request.typeOfSession)

        # Return one or many results SessionForms
        return SessionForms(
            items = [self._copyConferenceSessionToForm(
                sess) for sess in session])


        





  

api = endpoints.api_server([ConferenceApi]) 
