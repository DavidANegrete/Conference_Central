import json
import os
import time
import uuid

import endpoints
from google.appengine.api import urlfetch
from models import Profile

# Gets a users email or attempts to authenticate. 
def getUserId(user, id_type="email"):

    if id_type == "email":
        return user.email()

    if id_type == "oauth":
        """A workaround implementation for getting userid."""
        auth = os.getenv('HTTP_AUTHORIZATION')
        bearer, token = auth.split()
        token_type = 'id_token'
        if 'OAUTH_USER_ID' in os.environ:
            token_type = 'access_token'
        url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
               % (token_type, token))
        user = {}
        wait = 1
        for i in range(3):
            resp = urlfetch.fetch(url)
            if resp.status_code == 200:
                user = json.loads(resp.content)
                break
            elif resp.status_code == 400 and 'invalid_token' in resp.content:
                url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?%s=%s'
                       % ('access_token', token))
            else:
                time.sleep(wait)
                wait = wait + i
        return user.get('user_id', '')

    if id_type == "custom":
        # implement your own user_id creation and getting algorythm
        # this is just a sample that queries datastore for an existing profile
        # and generates an id if profile does not exist for an email
        profile = Conference.query(Conference.mainEmail == user.email())
        if profile:
            return profile.id()
        else:
            return str(uuid.uuid1().get_hex())


# Gets the user by invoking get_current_user()(GAE) and a user object is 
# returned if found, or an unauthorized exception is raised.
def getUser():
    user = endpoints.get_current_user()
    if not user:
        raise endpoints.UnauthorizedException('Authorization required (ERROR 401)')
    return user


# Checks if a field value is not filled out. 
# An endpoints exception is raised it's left empty.
def checkFieldValue(request):

    if not request:
        raise endpoints.BadRequestException(
              "Field required field.(ERROR 400)"
                )

def checkField(request, name):
    if not request:
        raise endpoints.BadRequestException(
              "'" + name + "' is a required field.(ERROR 400)"
                )

# Checks if a users ID and the ID of an ndb object are the not the same.  
# When they are not a forbidden exception is raised.
def checkUsers(userID, obj):
    if userID != obj.organizerUserId:
        raise endpoints.ForbiddenException(
            user_id + " is not not permitted to proceed with the request \
            (ERROR 403)")


# Gets a valid ndb key or raises an exception  
# Passed to this method is the request.name 
def getParentKey(request):
    try:
        _key = ndb.Key(urlsafe=request)
    except Exception:
        raise endpoints.BadRequestException(
            'Key error. (Error 400)')
    return _key

# Returns an error is the key provided is not good
# Accepts two variables the request object and the name
def checkObj(object, name):
        if not object:
            raise endpoints.NotFoundException(
                'No ' + name + ' found with the key provided.'
                 )