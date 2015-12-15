App Engine application for the Udacity training course.

# Conference Central
This App was worked and extra modules were added to enhance the original 
version, as required for a Udacity Nano Degree

# Design
#### Sessions
Sessions are added bonuses to a Conference and they are also ancestors of
Conferences. Sessions have two requeired fiels and they are 'name' and 'parentkey' and only the Conference creator can add a Session.

The Session ndb.model stores a Session Object this object has a 'has-a'
relationship with the Conference object. This is an extension of the 
Conference  object. It has six string field properties, two are
required, one integer.
 
StringProperty:
	REQUIRED:
		(name)
			- Used to save a sessions name.

		(parentKey)
        	- Represents the parent Conference key, creates the has-a relationship between a session and its parent Conference.     

	OPTIONAL:
    	(highlights)
        	- Saves the description of the things that make a session special
    	
    	(speakerID) 
        	- Saves the speaker key.
    	
    	(typeOfSession)
          	default value: 'GENERAL'

	        - Saves type of session (ex. workshop, tutorial). By default
	          it's set to 'GENERAL' which represents the default option in
	          the SessionType(enumeration) object.

IntegerProperty:
	OPTIONAL:
		(duration)
			- Save the amount of time in minutes a session will take.
DateProperty:
	OPTIONAL:
	    (date)
	    	- Stores the date a session will be on.
TimeProperty:
	OPTIONAL:
	    (startTime)
		    - Will be used to represent the sessions start time in 24 hr notation.
#### Speakers
	Speakers are sole entities so they are not related to any one Conference
	or session. To be used though the speakerID is used to assign them to a session.

The Speaker ndb.model stores a Speaker Object it is a sole entity and can be related to one or many Session Objects. The Speaker ndb.model has 5 string field properties two are required.
 
StringProperty:
	REQUIRED:
		(name)
           - Represents the name of a speaker.
   OPTIONAL:
       (bio)
           - Is an overview of the speaker. 
       (company)
           - Holds one or many companies a speaker works or has worked for.
       (projects)
           - A list of projects that speaker has accomplished

#### Featured Speakers
A featured is as a speaker that is assigned to two or more
sessions within a conference.  When a session is created within
`_createSessionObject()`, a check is performed on each **speakerKey** that is passed in. When a speaker is added to a Session a check is performed to see if they are a featured speaker.

#### User Wish Lists
A User can add sessions to their wish list using `addSessionToWishlist()` and passing in the session key. This is saved in the users Profile as a repeated field and is one of several changes made to the code since forking the original.

#### Additional Queries
- `getSpeakersByConference()` Accepts a Conference Key returns all Speakers.

- `getConferenceByDate()` Accepts a date and returns all Conferences on that day.

#### Query Problem Solution
**Question posed in project:** Let’s say that you don't like workshops and you
don't like sessions after 7 pm. How would you handle a query for all non-
workshop sessions before 7 pm? What is the problem for implementing this query?
What ways to solve it did you think of?

#### Query Problem Solution
**Let’s say that you don't like workshops and you
don't like sessions after 7 pm. How would you handle a query for all non-
workshop sessions before 7 pm? What is the problem for implementing this query? What ways to solve it did you think of?**

They query has to be seperated because you can not have two inequality filters on the same query. You would have to append to the query.
 
## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting
   your local server's address (by default [localhost:8080][5].)
1. Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.


[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
