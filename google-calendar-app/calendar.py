from __future__ import print_function
import httplib2
import os

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import appdaemon.plugins.hass.hassapi as hass
import datetime
import time

class calendar(hass.Hass):


  def initialize(self):
    self.SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
    self.CLIENT_SECRET_FILE = self.args["credential_dir"] + self.args["client_secret_file"]
    self.APPLICATION_NAME = 'Google Calendar API Python Quickstart'
    runtime = datetime.datetime.now() + datetime.timedelta(seconds=5)
    self.herinneringslist = []
    refreshtime= 60 * 60
    if "refreshtime" in self.args:      
        refreshtime = int(self.args["refreshtime"])
    self.debug = False    
    if "debug" in self.args:
        self.debug = self.args["debug"]
    if self.debug:
        self.log("init untill run_every done","DEBUG")
    self.run_every(self.controleer_agenda,runtime,refreshtime) 
    if self.debug:
        self.log("run_every initialised","DEBUG")
    self.controleer_agenda(self)       

  def controleer_agenda(self,kwargs):
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    ###############################################################
    # check if the credentials are set
    ###############################################################
    if self.debug:
        self.log("starting credential check","DEBUG")
    credentials = self.get_credentials()
    if self.debug:
        self.log("get credentials done, now authorize","DEBUG")
    http = credentials.authorize(httplib2.Http())
    if self.debug:
        self.log("authorize done, now build discovery","DEBUG")
    service = discovery.build('calendar', 'v3', http=http)
    ###############################################################
    # build the base from the html file
    ###############################################################
    HTMLfile = "<body style = '" + self.args["body_style"] + "'><table style = '" + self.args["table_style"] + "'>" 
    ###############################################################
    # try to get the data from google calendar
    ###############################################################
    try:
        if self.debug:
            self.log("trying to get the events","DEBUG")
        eventsResult = service.events().list(
            calendarId=self.args["calendarid"], timeMin=now, maxResults=int(self.args["amount"]), singleEvents=True,
            orderBy='startTime').execute()
        if self.debug:
            self.log("did get the events as expected","DEBUG")
    except:
        ###############################################################
        # google could not be reached so close the htmlfile
        ###############################################################
        if self.debug:
            self.log("problem with getting events, trying to save html","DEBUG")
        HTMLfile = HTMLfile +"<tr>" + self.args["not_reachable"] + "</tr></table></body>"
        self.writedash(HTMLfile)
        if self.debug:
            self.log("html saved correctly","DEBUG")
        return
    ###############################################################
    # get the events from the retrieved data
    ###############################################################
    events = eventsResult.get('items', [])
    if not events:
        ###############################################################
        # there are no events so close the htmlfile
        ###############################################################
        if self.debug:
            self.log("no events, trying to save html","DEBUG")
        HTMLfile = HTMLfile +"<tr>" + self.args["no_events"] + "</tr></table></body>"
        self.writedash(HTMLfile)
        if self.debug:
            self.log("html saved correctly","DEBUG")
        return

    if self.debug:
        self.log("starting to get and translate eventdata","DEBUG")
    previous_date = ""
    for event in events:
        ###############################################################
        # loop trough the retrieved events and build the rows
        ###############################################################
        actualtime = datetime.datetime.now()
        date_now = actualtime.strftime("%Y-%m-%d")
        try:
            ###############################################################
            # get the start date and time from the data
            ###############################################################
            start_date = datetime.datetime.strptime(event['start']['dateTime'][:-6],"%Y-%m-%dT%H:%M:%S")
            startdate = start_date.strftime("%Y-%m-%d")
            starttime = start_date.strftime(self.args["time_style"])
        except:
            ###############################################################
            # there was no start time so just get the date
            ###############################################################
            start_date = datetime.datetime.strptime(event['start']['date'],"%Y-%m-%d")
            startdate = event['start']['date']
            starttime = ""
        ###############################################################
        # change the date and day to how its shown in the html
        ###############################################################
        start_date_text = start_date.strftime(self.args["date_style"])
        start_day = start_date.strftime("%A")
        try:
            ###############################################################
            # try to get an end date and a endtime
            ###############################################################
            end_date = datetime.datetime.strptime(event['end']['dateTime'][:-6],"%Y-%m-%dT%H:%M:%S")
            enddate = end_date.strftime("%Y-%m-%d")
            endtime = " - " + end_date.strftime(self.args["time_style"])
        except:
            ###############################################################
            # no enddate and time so set defaults
            ###############################################################
            enddate = event['end']['date']
            endtime = ""
        ###############################################################
        # build the day head if needed
        ###############################################################
        if previous_date != start_date and startdate == date_now:
            ###############################################################
            # the first event for today
            ###############################################################
            head = "<tr><td style='" + self.args["day_head_style"] + "' colspan='2'><b>" + self.args["today_title"] + " ("+start_date_text+")</b></td></tr>"
            previous_date = start_date
        elif previous_date != start_date and startdate != date_now:
            ###############################################################
            # the first event for another day
            ###############################################################
            head = "<tr><td style='" + self.args["day_head_style"] + "' colspan='2'><b>" + start_day + " ("+start_date_text+")</b></td></tr>"
            previous_date = start_date
        else:
            ###############################################################
            # no new day head
            ###############################################################
            head = ""
        summary = event['summary']
        eventid = event['id']

        ###############################################################
        # check if there is a remindertime, if not set to 0
        ###############################################################
        try:
            reminder = event['reminders']['overrides'][0]
        except:
            reminder = {"minutes":"0"}
        reminderminutes = int(reminder.get("minutes"))
        if reminderminutes > 0:
            remindertext = "(-" + str(reminderminutes) + ")"
        else:
            remindertext = ""
        remindertime = start_date - datetime.timedelta(seconds=reminderminutes * 60)

        ###############################################################
        # check for reminders and use TTS (this part can be deleted for most people)
        ###############################################################
        remind = False
        if "reminder_TTS" in self.args:
            remind = self.args["reminder_TTS"]
        if remind:
            if remindertime != start_date and eventid not in self.herinneringslist:
                timediff = remindertime - actualtime
                self.run_at(self.remember, remindertime, summary = summary, reminderminutes=str(reminderminutes))
                self.herinneringslist.append(eventid)
                self.log("start herinnering: " + str(remindertime) + " Start: " + startdate + " " + starttime + " afspraak: " + summary)
        ###############################################################
        # check if it is a garbage collection calendar (this part can be deleted for most people)
        ###############################################################
        garbage_collection = False
        if "garbage_collection_calendar" in self.args:
            garbage_collection = self.args["garbage_collection_calendar"]
        if garbage_collection:
            if self.args["garbage_collection_checktext"] in summary:
                start_date = start_date + datetime.timedelta(days=1)
                summary = summary.replace(self.args["garbage_collection_deletetext"],"")
        ###############################################################
        # build the message line with the gathered info
        ###############################################################
        HTMLfile = HTMLfile + head + "<tr><td style = '" + self.args["time_css_style"] + "'>" + starttime + endtime + remindertext + "</td><td style = '" + self.args["message_style"] + "'>" + summary + "</td></tr>"
        if self.debug:
            self.log("an event is translated correctly","DEBUG")
    ###############################################################
    # close the HTML file, translate the days and save it
    ###############################################################
    HTMLfile = HTMLfile + "</table>"
    HTMLfile = self.translate_days(HTMLfile)    
    if self.debug:
        self.log("trying to save the html","DEBUG")
    self.writedash(HTMLfile)
    if self.debug:
        self.log("html saved correctly","DEBUG")

  def translate_days(self,text):
    ###############################################################
    # translate the days
    # returns: the translated file
    ###############################################################
    text = text.replace("Monday",self.args["days"]["Monday"])
    text = text.replace("Tuesday",self.args["days"]["Tuesday"])
    text = text.replace("Wednesday",self.args["days"]["Wednesday"])
    text = text.replace("Thursday",self.args["days"]["Thursday"])
    text = text.replace("Friday",self.args["days"]["Friday"])
    text = text.replace("Saturday",self.args["days"]["Saturday"])
    text = text.replace("Sunday",self.args["days"]["Sunday"])
    return text

  def writedash(self,htmltext):
    ###############################################################
    # save the HTML file
    ###############################################################
      try:
        log = open(self.args["htmlfile"], 'w')
        log.write(htmltext)
        log.close()
      except:
        self.log("HTML FILE CANT BE WRITTEN!!")


  def get_credentials(self):
    ###############################################################
    # Gets valid user credentials from storage.
    # If nothing has been stored, or if the stored credentials are invalid,
    # the OAuth2 flow is completed to obtain the new credentials.
    # Returns: Credentials, the obtained credential.
    ###############################################################
    home_dir = os.path.expanduser('~')
    credential_dir = self.args["credential_dir"]
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, self.args["client_secret_file"])
    if self.debug:
        self.log("credentialpath: {}".format(credential_path),"DEBUG")
    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        if self.debug:
            self.log("no valid credentials, so get them","DEBUG")
        flow = client.flow_from_clientsecrets(self.CLIENT_SECRET_FILE, self.SCOPES)
        flow.user_agent = self.APPLICATION_NAME
        credentials = tools.run_flow(flow, store, flags)
        if self.debug:
            self.log('Storing credentials to ' + credential_path,"DEBUG")
    return credentials

  def remember(self,kwargs):
    ###############################################################
    # speaks the reminder with TTS
    # works only if the soundfunctions app is installed and running
    ###############################################################
    if self.debug:
        self.log("this can only work if soundfunctions is installed","DEBUG")
    speaktext = ("ik heb een herinnering voor: " + kwargs["summary"] + " in " + kwargs["reminderminutes"] + " minuten.")
    sound = self.get_app("soundfunctions")
    sound.say(speaktext,"nl","1")
    self.log(speaktext)
