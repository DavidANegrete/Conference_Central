#!/usr/bin/env python

from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForms
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionType
from models import Speaker
from models import SpeakerForm
from models import SpeakerForms
from models import TeeShirtSize
from models import StringMessage

from utils import getUserId
from utils import getUser
from utils import checkFieldValue
from utils import checkField
from utils import checkUsers
from utils import checkObj
from utils import getParentKey

from settings import WEB_CLIENT_ID

import logging

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints
$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $
created by wesc on 2014 apr 21
"""

__author__ = 'wesc+api@google.com (Wesley Chun)',
'danegrete79@gmail.com(gritzMCgritz)'

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID

# Memcache keys
MEMCACHE_ANNOUNCEMENTS_KEY    = "RECENT_ANNOUNCEMENTS"
MEMCACHE_FEATURED_SPEAKER_KEY = "FEATURED_SPEAKER"

# - - - FormField Constants/Default Values - - - - - - - - - - - - - - - - - -

# Used when a conference form is left blank.
CONFERENCE_DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
    }

# Used with the Session Objects.
SESSION_DEFAULTS = {
    "duration": 0,
    "typeOfSession": SessionType.GENERAL,
    }

# Used to fill the Conference query operands.
OPERATORS = {
    'EQ': '=',
    'GT': '>',
    'GTEQ': '>=',
    'LT': '<',
    'LTEQ': '<=',
    'NE': '!='
    }

# used to create fields for the object
FIELDS = {
        'CITY': 'city',
        'TOPIC': 'topics',
        'MONTH': 'month',
        'MAX_ATTENDEES': 'maxAttendees',
        }

# - - - Resource Containers - - - - - - - - - - - - - - - - - - - - - - - - -

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage, websafeConferenceKey=messages.StringField(1))

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm, websafeConferenceKey=messages.StringField(1))

CONF_GET_BY_DATE = endpoints.ResourceContainer(
    message_types.VoidMessage, date = messages.StringField(1))

#SESH_POST_REQUEST = endpoints.ResourceContainer(
 #   SessionForm, websafeConferenceKey=messages.StringField(1))

SESSION_GET_REQUEST_BY_TYPE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey = messages.StringField(1, required=True),
    typeOfSession        = messages.StringField(2, required=True))

SESSION_BY_DATE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey = messages.StringField(1, required=True),
    date                 = messages.StringField(2, required=True))

GET_SPEAKERS_BY_CONFERENCE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey = messages.StringField(1, required=True))

SESH_BY_TIME_AND_TYPE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey = messages.StringField(1, required=True),
    noLaterThen          = messages.StringField(2, required=True),
    typeOfSession        = messages.StringField(3, required=True))

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    webSafeSessionKey = messages.StringField(1, required=True))

GET_FEATURED_SPEAKER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    webSafeSessionKey = messages.StringField(1, required=True))
# - - - Conference API  - - - - - - - - - - - - - - - - - - - - - - - - - - -

@endpoints.api(
    name='conference',
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
        
                    setattr(pf, field.name,
                            getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        
        pf.check_initialized()
        
        return pf

    def _getProfileFromUser(self):
        """Return user Profile from DataStore or create add new one if
        non-existent."""

        # Getting and Verifying current user
        user = getUser()
        
        # get the user_id (email) 
        user_id = getUserId(user)

        # Creating a profile key. 
        p_key = ndb.Key(Profile, user_id)
        
        # Using the profile key to get a profile Object
        profile = p_key.get()

        # create new Profile if not there
        if not profile:
            
            profile=Profile(
                key=p_key,
                displayName=user.nickname(),
                mainEmail=user.email(),
                teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED),)
            
            profile.put()
        
        return profile 

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
 
                        if field == 'teeShirtSize':
 
                            setattr(prof, field, str(val).upper())
 
                        else:
 
                            setattr(prof, field, val)
            prof.put()
        
        # return ProfileForm
        return self._copyProfileToForm(prof)

# - - - EndPoints Methods (Profile) - - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(
        message_types.VoidMessage, 
        ProfileForm,
        path='profile',
        http_method='GET',
        name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        
        return self._doProfile()

    @endpoints.method(
        ProfileMiniForm,
        ProfileForm,
        path='profile',
        http_method='POST',
        name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        
        return self._doProfile(request)

# - - - Conference objects  - - - - - - - - - - - - - - - - - - - - - - - - -

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
        """Create a Conference object, returning ConferenceForm/request."""
        
        # Getting and Verifying current user
        user = getUser()

        # get the user_id (email) 
        user_id = getUserId(user)

        # Checking if the name field is filled out. 
        checkFieldValue(request.name)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})
        
        # Getting deleted because they are not part of the ndb model
        del data['websafeKey']
        
        del data['organizerDisplayName']
        
        # add default values for those missing
        for df in CONFERENCE_DEFAULTS:
            
            if data[df] in (None, []):
            
                data[df] = CONFERENCE_DEFAULTS[df]
            
                setattr(request, df, CONFERENCE_DEFAULTS[df])
        
        # convert dates TO strings using the Date objects
        if data['startDate']:
            
            data['startDate'] = datetime.strptime(
                                    data['startDate'][:10], "%Y-%m-%d").date()
            
            data['month'] = data['startDate'].month
        
        else:
            
            data['month'] = 0
        
        if data['endDate']:
        
            data['endDate'] = datetime.strptime(
                data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
        
            data["seatsAvailable"] = data["maxAttendees"]

        #---- Generate a Profile Key based on user ID and Conference ----
        
        # Profile key
        p_key = ndb.Key(Profile, user_id)

        # allocate new Conference ID with Profile key as parent
        c_id  = Conference.allocate_ids(size=1, parent=p_key)[0]

        # make Conference key using p_key and c_id 
        c_key = ndb.Key(Conference, c_id, parent=p_key)

        # Update stored conference with profile and conference key
        data['key'] = c_key
        
        data['organizerUserId'] = request.organizerUserId = user_id
        
        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        
        # cron job
        taskqueue.add(
            
            params = {
                'email'   : user.email(),
                'subject' : 'You Created a New Conference!',
                'body'    : 'Here are the details for your conference:',
                'info'    : repr(request)},
            
            url    = '/tasks/send_confirmation_email')    
        
        return request

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        """Update a Conference object, returning the updated ConferenceForm().
        """
        # Getting and Verifying current user
        user = getUser()

        # get the user_id (email) 
        user_id = getUserId(user)

        # copy data from ProtoRPC Message into dict
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        
        # check that conference exists
        checkObj(conf, 'Conference')
        
        # To modify you must be the owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can modify the Conference.')

        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)

            # only copy fields where we get data
            if data not in (None, []):
                
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    
                    if field.name == 'startDate':

                        conf.month = data.month
                
                # write to Conference object
                setattr(conf, field.name, data)
        
        conf.put()
        
        prof = ndb.Key(Profile, user_id).get()
        
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

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
            
            formatted_query = ndb.query.FilterNode(filtr["field"],
                                                   filtr["operator"],
                                                   filtr["value"])
            q = q.filter(formatted_query)
        
        return q

    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        
        formatted_filters = []
        
        inequality_field = None
        
        for f in filters:
            
            filtr = ({field.name: getattr(f, field.name)
                     for field in f.all_fields()})
            
            try:
            
                filtr["field"]    = FIELDS[filtr["field"]]
            
                filtr["operator"] = OPERATORS[filtr["operator"]]
            
            except KeyError:
            
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")
            
            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":

                # Raise an exception if has been used before 
                if inequality_field and inequality_field != filtr["field"]:
                    
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                
                else:
                
                    inequality_field = filtr["field"]
            
            # Update formatted_fiters with new formatting
            
            formatted_filters.append(filtr)
        
        return (inequality_field, formatted_filters)

# - - - Endpoints Methods (Conference)  - - - - - - - - - - - - - - - - - - -

    @endpoints.method(
        ConferenceForm,
        ConferenceForm,
        path='conference',
        http_method='POST',
        name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    @endpoints.method(
        CONF_GET_REQUEST,
        ConferenceForm,
        path='conference/{websafeConferenceKey}',
        http_method='GET',
        name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""

        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        
        checkObj(conf, 'Conference')

        prof = conf.key.parent().get()
        
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    @endpoints.method(
        ConferenceQueryForms,
        ConferenceForms,
        path='queryConferences',
        http_method='POST',
        name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        
        conferences = self._getQuery(request)
        
        # get the organizers display name
        organisers = ([(ndb.Key(Profile, conf.organizerUserId)) for conf in
                      conferences])
        
        # get_multi is a model hook, uses memcache
        profiles = ndb.get_multi(organisers)
        
        # put display names in a dict for easier fetching
        names = {}
        
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items = [self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in conferences])

    @endpoints.method(
        message_types.VoidMessage,
        ConferenceForms,
        path='getConferencesCreated',
        http_method='POST',
        name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        
        # Getting and Verifying current user
        user = getUser()

        # get the user_id (email) 
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        conferences = Conference.query(ancestor=ndb.Key(Profile, user_id))
        
        prof = ndb.Key(Profile, user_id).get()
        
        # return one or many ConferenceForm objects
        return ConferenceForms(
            items = [self._copyConferenceToForm(
                conf, getattr(prof, 'displayName')) for conf in conferences])

    @endpoints.method(
        CONF_GET_BY_DATE,
        ConferenceForms,
        path='getConferencesByDate/{date}',
        http_method='GET',
        name='getConferencesByDate')
    def getConferencesByDate(self, request):
        """Given a Conference key and date return the associated Conference. 
        """
        
        # Getting and Verifying current user
        user = getUser()

        # get the user_id (email) 
        user_id = getUserId(user)

        conferences = Conference.query()

        # Convert the date string passed to a date Object
        date = datetime.strptime(request.date[:10], "%Y-%m-%d").date()

        # Get the Conferences
        conferences = conferences.filter(Conference.startDate == date)
        
        prof = ndb.Key(Profile, user_id).get()
        
        # return one or many ConferenceForm objects
        return ConferenceForms(
            items = [self._copyConferenceToForm(
                conf, getattr(prof, 'displayName')) for conf in conferences])

# - - - Session objects - - - - - - - - - - - - - - - - -

    def _copyConferenceSessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""

        sf = SessionForm()
        
        for field in sf.all_fields():
        
            if hasattr(session, field.name):
        
                # Convert date and startTime fields to strings
                if field.name == 'date' or field.name == 'startTime':
        
                    setattr(sf, field.name, str(getattr(session, field.name)))
        
                # Convert typeOfSession to enum
                elif field.name == 'typeOfSession':
                    
                    # set typeOfSession equal to enum 
                    setattr(
                        sf, field.name, getattr(
                            SessionType, getattr(session, field.name)))
                
                else:
                
                    setattr(sf, field.name, getattr(session, field.name))
            
            # Convert DataStore keys to URLSafe keys
            elif field.name == 'parentKey' or field.name == 'speakerKey':
            
                setattr(sf, field.name, session.key.urlsafe())
        
        sf.check_initialized()
        
        return sf

    def _createSessionObject(self, request):
        """Create a Session object, returning SessionForm/request."""
        
        # Getting and Verifying current user
        user = getUser()

        # get the user_id (email) 
        user_id = getUserId(user)

        # Check that the 'name' field if filed
        checkField(request.name, 'name')

        # Check that the 'parentKey' field if filed
        checkField(request.parentKey, 'parentKey')
        
        # Attempt to retrieve the Conference or raise an exception
        try:
            _key = ndb.Key(urlsafe=request.parentKey)
        except Exception:
            raise endpoints.BadRequestException(
                'The parentKey given is invalid.')
        
        # Retrieve the Conference Obj 
        conf = _key.get()
        
        # Verify that the current user created the conference
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the conference creator can add a session to it.')
        
        # Check speakerKey and save them
        speakers = []
        
        if request.speakerKey:
        
            for speakerKey in request.speakerKey:
        
                try:
                    speaker = ndb.Key(urlsafe=speakerKey).get()
                    speakers.append(speaker)
        
                except Exception:
                    raise endpoints.BadRequestException(
                        'Check the speakerKey it is invalid.')
        
        # Copy SessionForm/ProtoRPC Message into dict
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})
        
        # If values not given for Session defaults, add defaults
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
            data['month'] = conf.month
        
        # Convert startTime from string to Time object
        if data['startTime']:
        
            data['startTime'] = (datetime.strptime(
                                 data['startTime'][:5], "%H:%M").time())
        
         # Convert typeOfSession to string
        if data['typeOfSession']:
        
            data['typeOfSession'] = str(data['typeOfSession'])
        
        # Create a session id for the Session,
        # create the relationship with parent key.
        s_id = Session.allocate_ids(size=1, parent=_key)[0]
        
        # Create the session key
        s_key = ndb.Key(Session, s_id, parent=_key)
        
        # Fill the session key
        data['key'] = s_key
        
        # Check that the speaker was passed
        if speakers:

            #  Query the session for instance of speakers 
            s = Session.query(
                ancestor=ndb.Key(urlsafe=request.parentKey))
            
            # Setting none as featured
            featured = None
            
            # Number of session
            instance_count = 0

            for spkr in data['speakerKey']:
                
                i_count = s.filter(Session.speakerKey == spkr).count()
                
                if i_count >= instance_count:
                
                    featured = spkr
                
                    minSessions = i_count

            # Advise of the featured Speaker using the taskQueue
            if featured:
                taskqueue.add(
                    params = {
                        'websafeConferenceKey': request.parentKey,
                        'websafeSpeakerKey'   : featured},
                    url    = '/tasks/set_featured_speaker',
                    method = 'GET')

        # Store in the DataStore
        Session(**data).put()
        
        # Send an email to the conference organizer
        taskqueue.add(
            params = {
                'email'   : user.email(),
                'subject' : 'You Created a New Session for %s!' % conf.name,
                'body'    : 'Here are the details for new Session:',
                'info'    : repr(request)},
            url    = '/tasks/send_confirmation_email')
        return request


# - - - Endpoints Methods (Session)  - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(
        SessionForm,
        SessionForm,
        path='sessions',
        http_method='POST',
        name='createSession')
    def createSession(self, request):
        """Create a new Session."""
        
        return self._createSessionObject(request)

    @endpoints.method(
        CONF_GET_REQUEST,
        SessionForms,
        path='sessions/{websafeConferenceKey}',
        http_method='GET',
        name='getSessionsByConference')
    def getConferenceSessions(self, request):
        """Given a conference, return all sessions."""
        
        # Getting and Verifying current user
        user = getUser()
        
        # Retrieve the Conference key
        try:
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        except Exception:
            raise endpoints.BadRequestException(
                'The websafeConferenceKey given is invalid.')
        
        # Verify that the Conference exists
        conf = c_key.get()
        
        checkObj(conf, 'Conference')

        # Store Sessions that are ancestors
        sessions = Session.query(ancestor=c_key)
        
        # Return a SessionForm for each Session
        return SessionForms(
            items = [self._copyConferenceSessionToForm(
                sess) for sess in sessions])

    @endpoints.method(
        SESSION_GET_REQUEST_BY_TYPE,
        SessionForms,
        path='getConferenceSessionsByType/'
        '{websafeConferenceKey}/{typeOfSession}',
        http_method='GET',
        name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Given a conference and session type, return matching sessions."""
        
        # Confirm the user is authorized
        user = getUser()

        # First query for a session with specified key
        sessions = Session.query(
            ancestor=ndb.Key(urlsafe=request.websafeConferenceKey))
        
        # Second query for remaining Sessions by the type specified
        sessions = sessions.filter(
            Session.typeOfSession == request.typeOfSession)
        
        # Return a SessionForm for each Session
        return SessionForms(
            items = [self._copyConferenceSessionToForm(
                sess) for sess in sessions])


# - - - Speaker objects - - - - - - - - - - - - - - - - -

    def _copySpeakerToForm(self, speaker):
        """Copy relevant fields from Speaker to SpeakerForm"""
        
        sf = SpeakerForm()
        
        for field in sf.all_fields():
        
            if hasattr(speaker, field.name):
        
                setattr(sf, field.name, getattr(speaker, field.name))
        
            elif field.name == "websafeKey":
        
                setattr(sf, field.name, speaker.key.urlsafe())
        
        sf.check_initialized()
        
        return sf

    def _createSpeakerObject(self, request):
        """Create a Speaker object, returning SpeakerForm/request."""
        
        # Getting and Verifying current user
        user = getUser()

        # Confirm the field is filled out
        checkField(request.name, 'name')

        # Copy SpeakerForm/ProtoRPC Message into dict
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})

        # Create a key for the Speaker
        s_id  = Session.allocate_ids(size=1)[0]
        s_key = ndb.Key(Speaker, s_id)
        
        # Update stored session with session keys
        data['key'] = s_key
        
        # Create and update session and return the form
        Speaker(**data).put()
        
        taskqueue.add(
        
            params = {
                'email'   : user.email(),
                'subject' : 'You Added %s as a Speaker!' % data['name'],
                'body'    : 'Here are the details for the added speaker:',
                'info'    : repr(request)},
        
            url    = '/tasks/send_confirmation_email')
        
        return request

    @endpoints.method(
        SpeakerForm,
        SpeakerForm,
        path='speaker',
        http_method='POST',
        name='createSpeaker')
    def createSpeaker(self, request):
        """Create a Speaker."""
        
        return self._createSpeakerObject(request)

    @endpoints.method(
        CONF_GET_REQUEST,
        SpeakerForms,
        path=('getSpeakersByConference/{websafeConferenceKey}'),
        http_method='GET',
        name='getSpeakersByConference')
    def getSpeakersByConference(self, request):
        """Given a websafeConferenceKey, return all speakers."""
        
        # Getting and Verifying current user
        user = getUser()

        # Retrieve the Conference key
        try:
            
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        
        except Exception:
        
            raise endpoints.BadRequestException(
                'The websafeConferenceKey is invalid.')
        
        # Verify that the conference exists
        conference = c_key.get()

        checkObj(conference, 'Conference')

        # Save the ancestors the Conference obj
        sessions = Session.query(ancestor=c_key)
        
        # Retrieve Speaker Keys from each Session in a Conference
        speakerKeys = set()

        for sess in sessions:
            
            for webSafeKey in sess.speakerKey:
                
                speaker_key = ndb.Key(urlsafe=webSafeKey)
                
                # add to set
                speakerKeys.add(speaker_key)

        # Container to keep speaker objects
        speakers = []
        
        # Get each speaker and add to the set
        for spk in speakerKeys:
            
            speaker = spk.get()

            speakers.append(speaker)

        # Return one or many SpeakerForms for Speakers
        return SpeakerForms(
            items = [self._copySpeakerToForm(
                spkr) for spkr in speakers])

# - - - Featured Speakers - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheFeaturedSpeaker(self, request):
        """Finds the featured Speaker and adds the speaker 
        to the memcache."""



        # Retrieve the Conference key
        try:
            
            c_key = ndb.Key(urlsafe=request.websafeConferenceKey)
        
        except Exception:
        
            raise endpoints.BadRequestException(
                'The websafeConferenceKey is invalid.')
        
        # Verify that the conference exists
        conference = c_key.get()

        checkObj(conference, 'Conference')

        # Store the Sessions that are ancestors of the Conference
        sessions = Session.query(ancestor=c_key)

        # Retrieve Speaker Keys from each Session in a Conference
        speakerKeys = set()






        #memcache.set(MEMCACHE_FEATURED_SPEAKER_KEY, featured)
        return featured

    @endpoints.method(
        GET_FEATURED_SPEAKER,
        StringMessage,
        path='getFeaturedSpeaker/{websafeConferenceKey}',
        http_method='GET',
        name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return Featured Speaker from memcache."""

        # Getting and Verifying current user
        user = getUser()
        
        # return an existing Featured Speaker from Memcache or an empty string.
        featured = memcache.get(MEMCACHE_FEATURED_SPEAKER_KEY)
        if not featured:
            featured = ""
        return StringMessage(data=featured)

# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        
        retval = None
        
        # Get the Profile
        prof = self._getProfileFromUser()
        
        # Check if the conference exists given a websafeConferenceKey
        wsck = request.websafeConferenceKey
        
        # get the conference object.
        conf = ndb.Key(urlsafe=wsck).get()
        
              # Check if the conf was retrieved
        checkObj(conf, 'Conference')

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")
            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")
            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True
        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False
        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path        = 'conferences/attending',
                      http_method = 'GET',
                      name        = 'getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser()  # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in
                     prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)
        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in
                      conferences]
        profiles = ndb.get_multi(organisers)
        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId])
                for conf in conferences])

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
                      path        = 'conference/{websafeConferenceKey}',
                      http_method = 'POST',
                      name        = 'registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
                      path        = 'conference/{websafeConferenceKey}',
                      http_method = 'DELETE',
                      name        = 'unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache.
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])
        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = '%s %s' % (
                'Last chance to attend! The following conferences '
                'are nearly sold out:',
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)
        return announcement

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path        = 'conference/announcement/get',
                      http_method = 'GET',
                      name        = 'getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        # return an existing announcement from Memcache or an empty string.
        announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
        if not announcement:
            announcement = ""
        return StringMessage(data=announcement)

# - - - wishList methods - - - - - - - - - - - - - - - - - - -

    def _sessionWishlist(self, request, add=True):
        """Add or remove a session to a User's wishlist."""
        retval = None
        # Ensure that user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization Required')
        # Get user's profile
        prof = self._getProfileFromUser()
        # Get Session being passed
        try:
            sesh_key = ndb.Key(urlsafe=request.webSafeSessionKey)
        except Exception:
            raise endpoints.BadRequestException(
                'The websafeSessionKey given is invalid.')
        session = sesh_key.get()
        # Throw Not Found Error if no Session found
        if not sesh_key:
            raise endpoints.NotFoundException(
                'No session found with key: {0}'.format(sesh_key))
        # Get Session parent key and associated Conference
        conference = session.key.parent().get()
        conf_key = conference.key.urlsafe()
        # Ensure that conference is in User's conferenceKeysToAttend
        if conf_key not in prof.conferenceKeysToAttend:
            raise ConflictException(
                "You must be register for the parent confernce before adding "
                "a session to your wishlist.")
        if add:
            # Check if session is already in wishlist
            if request.webSafeSessionKey in prof.sessionWishList:
                raise ConflictException(
                    "This Session is already in your wishlist.")
            # Add session to User's wishlist
            prof.sessionWishList.append(request.webSafeSessionKey)
            retval = True
        else:
            # Check if session is already in wishlist
            if request.webSafeSessionKey in prof.sessionWishList:
                # Remove Session from User's wishlist
                prof.sessionWishList.remove(request.webSafeSessionKey)
                retval = True
            else:
                retval = False
        prof.put()
        return BooleanMessage(data=retval)

    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path        = 'view/session_wishlist',
                      http_method = 'GET',
                      name        = 'getSessionWishlist')
    def getSessionWishlist(self, request):
        """Get list of sessions in the current user's wishlist."""
        # Get user's profile
        prof = self._getProfileFromUser()
        sesh_keys = [ndb.Key(urlsafe=wssk) for wssk in
                     prof.sessionWishList]
        sessions = ndb.get_multi(sesh_keys)
        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copyConferenceSessionToForm(
                sesh) for sesh in sessions])

    @endpoints.method(SESSION_POST_REQUEST, BooleanMessage,
                      path        = 'sessionToWishlist/{webSafeSessionKey}',
                      http_method = 'POST',
                      name        = 'addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add a session to the User's wishlist."""
        return self._sessionWishlist(request)

    @endpoints.method(SESSION_POST_REQUEST, BooleanMessage,
                      path        = 'removeSessionFromWishlist/'
                                    '{webSafeSessionKey}',
                      http_method = 'DELETE',
                      name        = 'removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """Remove a session from the User's wishlist."""
        return self._sessionWishlist(request, add=False)






api = endpoints.api_server([ConferenceApi])  # register API