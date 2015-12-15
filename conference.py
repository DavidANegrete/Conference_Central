#!/usr/bin/env python

from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import TeeShirtSize
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionType
from models import Speaker
from models import SpeakerForm
from models import SpeakerForms
from models import StringMessage
from models import ConflictException

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

MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
MEMCACHE_SPEAKER_KEY = "FEATURED_SPEAKER"

ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')

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

CONFERENCE_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm, websafeConferenceKey=messages.StringField(1))

CONFERENCE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage, websafeConferenceKey=messages.StringField(1))

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm, websafeConferenceKey=messages.StringField(1),
    webSafeSessionKey = messages.StringField(2, required=True))

SESSION_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage, websafeConferenceKey=messages.StringField(1))

SESSION_GET_REQUEST_BY_TYPE = endpoints.ResourceContainer(
    message_types.VoidMessage,
    typeOfSession=messages.StringField(2, required=True),
    websafeConferenceKey=messages.StringField(1))

SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage, speakerID=messages.StringField(1))

SPEAKER_GET_ALL = endpoints.ResourceContainer(message_types.VoidMessage,)


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
                    setattr(
                        pf, field.name,
                        getattr(TeeShirtSize, getattr(prof, field.name))
                        )
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf

    def _getProfileFromUser(self):
        """Return user Profile from DataStore, creating new one if non-existent.
        """
        # Verifying the current user is authorized
        # if so a user object is returned,
        # or an exception is raised if not authorized.
        user = getUser()

        # Returning the user id (email)
        user_id = getUserId(user)

        # Using the users retrieved email and an ndb.key is returned.
        p_key = ndb.Key(Profile, user_id)

        # p_key.get(), returns a users profile from DataStore.
        profile = p_key.get()

        # Create new Profile if not found.
        if not profile:
            # Profile object is created.
            profile = Profile(
                key=p_key,
                displayName=user.nickname(),
                mainEmail=user.email(),
                teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED),
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
        """Create or update Conference object, returning ConferenceForm/request.
        """

        # Checking if the user if is signed if not an exception is raised
        # imported from utils.py
        user = getUser()

        # Returning the user id (email)
        user_id = getUserId(user)

        # Checking if the name field is filled or throwing an error.
        # The checks if a field is filled or an Exception is raised.
        # Passed to it is the request and the string value of the field.
        checkFieldValue(request.name)

        # Copying the ConferenceForm/ProtoRPC Message
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # adding default values for those missing data & outbound Message
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

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(
            params={
                'email': user.email(),
                'subject': 'You Created a New Conference!',
                'body': 'Here are the details for your conference:',
                'info': repr(request)},
            url='/tasks/send_confirmation_email')
        return request

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        """Update a Conference object, returns the updated ConferenceForm
        """

        # Verifying the current user is authorized
        # if so a user object is returned,
        # or an exception is raised if not authorized.
        user = getUser()

        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()

        # Check if it is real or raise an exception
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found (ERROR 404)'
                % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

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


# - - - Endpoints Methods (Conference)  - - - - - - - - - - - - - - - - - - -

    # post request to create a new Conference
    @endpoints.method(
        ConferenceForm,
        ConferenceForm,
        path='conference',
        http_method='POST',
        name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    # Returns all conferences created
    @endpoints.method(
        ConferenceQueryForms,
        ConferenceForms,
        path='queryConferences',
        http_method='POST',
        name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # Get displayName from profiles
        # using get_multi for speed
        organisers = ([(ndb.Key(Profile, conf.organizerUserId))
                       for conf in conferences])
        profiles = ndb.get_multi(organisers)

        # put names in a dictionary for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in conferences])

    @endpoints.method(
        message_types.VoidMessage,
        ConferenceForms,
        path='getConferencesCreated',
        http_method='POST',
        name='getConferencesCreated')
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
            items=[self._copyConferenceToForm(
                conf, getattr(prof, 'displayName')) for conf in conferences])

    @endpoints.method(
        CONFERENCE_GET_REQUEST, ConferenceForm,
        path='conference/{websafeConferenceKey}',
        http_method='GET',
        name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s'
                % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
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
            formatted_query = ndb.query.FilterNode(
                filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q

    # This method checks the the supplied filters filters  information
    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {
                field.name: getattr(f, field.name)for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used before
                # not allowed if inequality was used before ih the query
                # track the field where inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
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
                    setattr(
                        s_form, field.name, str(getattr(session, field.name)))

                # Convert to enumeration value type
                elif field.name == 'typeOfSession':
                    setattr(
                        s_form, field.name, getattr(
                            SessionType, getattr(session, field.name)))

                # Just copy over the fields
                else:
                    setattr(s_form, field.name, getattr(session, field.name))

            # Convert DataStore keys to URL compatible strings
            elif field.name == 'parentKey':
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
        # _key = getParentKey(request.parentKey)
        try:
            _key = ndb.Key(urlsafe=request.parentKey)
        except Exception:
            raise endpoints.BadRequestException('Key error. (Error 400)')

        # Get a Conference object from DataStore
        con_object = _key.get()

        # Verify that the current user created the Conference
        # or a Forbidden Exception is raised.
        checkUsers(user_id, con_object)

        # This is where all the speakers will be saved
        speakers = []
        # Check for the key
        if request.speakerKey:
            for speakerKey in request.speakerKey:
                try:
                    speaker = ndb.Key(urlsafe=speakerKey).get()
                    speakers.append(speaker)
                except Exception:
                    raise endpoints.BadRequestException(
                        'speakerKey {0} is invalid.'.format(speakerKey))

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

            # Step through to check the dic
            for speaker in data['speakerKey']:
                
                # Get the count in the DB
                count = s.filter(Session.speakerKey == speaker).count()
                
                if count >= instance_count:
                    featured = speaker
                    instance_count = count
            if featured:
                taskqueue.add(
                    params={
                        'websafeConferenceKey': request.parentConfKey,
                        'websafeSpeakerKey': featured},
                    url='/tasks/set_featured_speaker',
                    method='GET')
            


        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Session(**data).put()
        taskqueue.add(
            params={
                'email': user.email(),
                'subject': 'You added a New Session!',
                'body': 'This is the Session name: %s' % con_object.name,
                'info': repr(request)},
            url='/tasks/send_confirmation_email')
        return request

# - - - Endpoints Methods (Session)  - - - - - - - - - - - - - - - - - - - -

    # post request to create a new Session
    @endpoints.method(
        SessionForm,
        SessionForm,
        path='createSession',
        http_method='POST',
        name='createSession')
    def createSession(self, request):
        """Create s new Session."""
        return self._createSessionObject(request)

    @endpoints.method(
        SESSION_GET_REQUEST,
        SessionForms,
        path='sessions/{websafeConferenceKey}',
        http_method='GET',
        name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Given a conferencekey, return the sessions."""

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
            items=[
                self._copyConferenceSessionToForm(sess) for sess in sessions])

    # Given a Conference returns all session of a specified type.
    @endpoints.method(
        SESSION_GET_REQUEST_BY_TYPE,
        SessionForms,
        path='getConferenceSessionsByType/'
        '{websafeConferenceKey}/{typeOfSession}',
        http_method='GET',
        name='getConferenceSessionsByType')
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
            items=[
                self._copyConferenceSessionToForm(sess) for sess in session])


# - - - Speaker objects - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _copySpeakerToForm(self, request):
        """Copy relevant fields from Speaker to SpeakerForm."""
        s_form = SpeakerForm()
        for field in s_form.all_fields():

            # Checking if the request has name filled
            if hasattr(request, field.name):

                # if so setting the values on the form
                setattr(s_form, field.name, getattr(request, field.name))

            # Checking for a websafeKey exists
            elif field.name == "speakerID":

                # if so setting the values on the form
                setattr(s_form, field.name, request.key.urlsafe())

        # Checks that all required fields are initialized
        s_form.check_initialized()
        return s_form

    def _createSpeakerObject(self, request):
        """Create a Speaker object, returning SpeakerForm/request."""

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

        # Copy Speaker or ProtoRPC to a dictionary
        data = ({field.name: getattr(request, field.name)
                for field in request.all_fields()})

        # Allocates an ID for the model.
        _id = Session.allocate_ids(size=1)[0]

        # returns the Key object for the instance
        _key = ndb.Key(Speaker, _id)

        # Update the dictionary with the key
        data['key'] = _key

        # create Speaker, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Speaker(**data).put()
        taskqueue.add(
            params={
                'email': user.email(),
                'subject': 'You Created a New Speaker!',
                'body': 'This is the speakers name: %s' % data['name'],
                'info': repr(request)},
            url='/tasks/send_confirmation_email')

        return request

# - - - Endpoints Methods (Speaker)- - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(
        SpeakerForm,
        SpeakerForm,
        path='speaker',
        http_method='POST',
        name='createSpeaker')
    def createSpeaker(self, request):
        """Create a new Speaker."""
        return self._createSpeakerObject(request)

    @endpoints.method(
        SPEAKER_GET_REQUEST,
        SessionForms,
        path='getSessionsBySpeaker/{speakerID}',
        http_method='GET',
        name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Given a speakerID, returns are all the Session instances of
        that respective speaker.
        """

        # Verifying if the current user is authorized
        # and a user object is returned
        # or an Unauthorized exception is raised.
        user = getUser()

        # Filter Sessions by speakerID
        sessions = Session.query(Session.speakerID == request.speakerID)

        # Return a SessionForm for each Session
        return SessionForms(
            items=[
                self._copyConferenceSessionToForm(sess) for sess in sessions])

    @endpoints.method(
        SPEAKER_GET_ALL,
        SpeakerForms,
        path='getSpeakers',
        http_method='GET',
        name='getSpeakers')
    def getSpeakers(self, request):
        """Return all speakers created."""

        # Verifying if the current user is authorized
        # and a user object is returned
        # or an Unauthorized exception is raised.
        user = getUser()

        # get all the queries
        q = Speaker.query()

        # return set of ConferenceForm objects per Conference
        return SpeakerForms(
            items=[self._copySpeakerToForm(f) for f in q])

# - - - Featured Speakers - - - - - - - - - - - - - - - - - - - - - - - - - - 
    
    @staticmethod
    def _memcacheFeaturedSpeaker(websafeConferenceKey, websafeSpeakerKey):
        """Assigns a speaker as featured and uses a memcache to notify"""

        # Get the websafeConferenceKey
        c_key = ndb.Key(urlsafe=websafeConferenceKey)
        conf = c_key.get()
        
        # Get the websafeSpeakerKey
        s_key = ndb.Key(urlsafe=websafeSpeakerKey)
        speaker = s_key.get()

        featured = speaker.name + "has been added as a featured speaker at " + conf.name
        
        memcache.set(MEMCACHE_SPEAKER_KEY, featured)
        return featured

    @endpoints.method(
        message_types.VoidMessage, StringMessage,
        path='featured_speaker/get',
        http_method='GET',
        name='getFeaturedSpeaker')
    def getFeaturedSpeaker(self, request):
        """Return Featured Speaker from memcache."""
        
        # return a Featured Speaker or an empty string.
        featured = memcache.get(MEMCACHE_SPEAKER_KEY)
        if not featured:
            featured = ""
        return StringMessage(data=featured)

# - - - Registration  - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""

        retval = None
        profile = self._getProfileFromUser()

        # Check the websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey

        # Try to get the get a Conference with the key
        conference = ndb.Key(urlsafe=wsck).get()

        # Gets a valid key or raises an exception
        if not conference:
            raise endpoints.NotFoundException(
                'No Conference found (ERROR 404)')

        # register
        if reg:

            # check if user already registered otherwise add
            if wsck in profile.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conference.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            profile.conferenceKeysToAttend.append(wsck)
            conference.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in profile.conferenceKeysToAttend:

                # unregister user, add back one seat
                profile.conferenceKeysToAttend.remove(wsck)
                conference.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # add back to the DataStore and Conference
        profile.put()
        conference.put()
        return BooleanMessage(data=retval)

    @endpoints.method(
        message_types.VoidMessage,
        ConferenceForms,
        path='conferences/attending',
        http_method='GET',
        name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""

        profile = self._getProfileFromUser()
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in
                     profile.conferenceKeysToAttend]

        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organizers = [ndb.Key(Profile, conf.organizerUserId) for conf in
                      conferences]
        profiles = ndb.get_multi(organizers)

        # add to dictionary
        names = {}

        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId])
                for conf in conferences])

    @endpoints.method(
        CONFERENCE_GET_REQUEST, BooleanMessage,
        path='conference/{websafeConferenceKey}',
        http_method='POST',
        name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)

    @endpoints.method(
        CONFERENCE_GET_REQUEST,
        BooleanMessage,
        path='conference/{websafeConferenceKey}',
        http_method='DELETE',
        name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference.
        """
        return self._conferenceRegistration(request, reg=False)


# - - - Announcements - - -  - - - - - - - - - - - - - - - - - - - - - - - - -

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

    @endpoints.method(
        message_types.VoidMessage,
        StringMessage,
        path='conference/announcement/get',
        http_method='GET',
        name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        # return an existing announcement from Memcache or an empty string.
        announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY)
        if not announcement:
            announcement = ""
        return StringMessage(data=announcement)


# - - - WishList - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - 

    def _sessionWishlist(self, request, add=True):
        """Add to wish list or remove from the Users wish list"""

        retval = None

        # Checking if the user if is signed 
        # if not an exception is raised
        user = getUser()

        # Using get ProfileFromUser retrieving the User Profile
        prof = self._getProfileFromUser()
        
        # From the request get the webSafeSessionKey or raise an exception
        try:
            sesh_key = ndb.Key(urlsafe=request.webSafeSessionKey)
        except Exception:
            raise endpoints.BadRequestException(
                'The websafeSessionKey given is invalid.')
        
        # Get the Session from the DataStore
        session = sesh_key.get()
        
        # If not raise an exception
        if not sesh_key:
            raise endpoints.NotFoundException(
                'No session found with key: {0}'.format(sesh_key))

        # Get the related entities
        conference = session.key.parent().get()

        # Get the URLSafe Conference key
        conf_key = conference.key.urlsafe()

        # Ensure that Conference is in conferenceKeysToAttend
        if conf_key not in prof.conferenceKeysToAttend:
            raise ConflictException(
                "Must be registered to add on the Wishlist.")
        
        # If a user opts to add.
        if add:

            # Confirm the user is signed up first. 
            if request.webSafeSessionKey in prof.sessionWishList:
                raise ConflictException(
                    "This Session is already in your wishlist.")
            
            # Add the wishlist item to the users profile
            prof.sessionWishList.append(request.webSafeSessionKey)
            retval = True
        
        # If the user wants to unregister
        else:

            # Check if session its alreay in the wish list
            if request.webSafeSessionKey in prof.sessionWishList:
                
                # Remove Session from the users Profile
                prof.sessionWishList.remove(request.webSafeSessionKey)
                retval = True
            else:
                retval = False
        prof.put()
        return BooleanMessage(data=retval)

    @endpoints.method(
        message_types.VoidMessage,
        SessionForms,
        path='view/session_wishlist',
        http_method='GET',
        name='getSessionWishlist')
    def getSessionWishlist(self, request):
        """Get list of sessions in the current user's wishlist."""

        # Checking if the user if is signed 
        # if not an exception is raised
        user = getUser()

        # Get user's profile
        prof = self._getProfileFromUser()

        # Get a session key from the Profile
        sesh_keys = [
                    ndb.Key(urlsafe=wssk) for wssk in
                    prof.sessionWishList
                    ]

        # Getting the session using get multi to lighten the load
        sessions = ndb.get_multi(sesh_keys)

        # return set of SessionForm objects per Session
        return SessionForms(
            items=[self._copyConferenceSessionToForm(
                sesh) for sesh in sessions])

    @endpoints.method(
        SESSION_POST_REQUEST,
        BooleanMessage,
        path='sessionToWishlist/{webSafeSessionKey}',
        http_method='POST',
        name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """Add a session to the User's wishlist passing a websafeSessionKey."""
        return self._sessionWishlist(request)

    @endpoints.method(
        SESSION_POST_REQUEST,
        BooleanMessage,
        path='removeSessionFromWishlist/'
        '{webSafeSessionKey}',
        http_method='DELETE',
        name='removeSessionFromWishlist')
    def removeSessionFromWishlist(self, request):
        """Remove a session from the User's wishlist."""
        return self._sessionWishlist(request, add=False)

api = endpoints.api_server([ConferenceApi])
