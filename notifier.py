#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Uploaded by juan_grande 2005/02/24 18:38 UTC
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import time
import os
import sys
import warnings
import ConfigParser
import xmllangs
import GmailConfig
import GmailPopupMenu
import gmailatom
import pynotify

ICON_PATH=sys.path[0]+"/icon.png"
ICON2_PATH=sys.path[0]+"/icon2.png"

def removetags(text):
	raw=text.split("<b>")
	raw2=raw[1].split("</b>")
	final=raw2[0]
	return final

def shortenstring(text,characters):
	if text == None: text = ""
	mainstr=""
	length=0
	splitstr=text.split(" ")
	for word in splitstr:
		length=length+len(word)
		if len(word)>characters:
			if mainstr=="":
				mainstr=word[0:characters]
				break
			else: break
		mainstr=mainstr+word+" "
		if length>characters: break
	return mainstr.strip()

class GmailNotify:

	configWindow = None
	options = None

	def __init__(self):
		self.init=0
		print "Gmail Notifier v1.6.1b ("+time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())+")"
		print "----------"
		# Configuration window
		self.configWindow = GmailConfig.GmailConfigWindow( )
		# Reference to global options
		self.options = self.configWindow.options
		# Check if there is a user and password, if not, load config window
		while ( self.options["gmailusername"] == None or self.options["gmailpassword"] == None ):
				self.configWindow.show()
		# Load selected language
		self.lang = self.configWindow.get_lang()
		print "selected language: "+self.lang.get_name()
		# Define some flags
		self.senddown=0
		self.popup=0
		self.newmessages=0
		self.mailcheck=0
		self.hasshownerror=0
		self.hassettimer=0 
		self.dont_connect=0
		self.unreadmsgcount=0
		# Define the timers
		self.maintimer=None
		self.popuptimer=0
		self.waittimer=0
		# Create the tray icon object
		self.tray = gtk.StatusIcon()
		self.tray.set_tooltip(self.lang.get_string(21))
		# Set the image for the tray icon
		self.tray.set_from_file(ICON_PATH)
		self.tray.connect('popup-menu',self.tray_icon_clicked)
		# Create the popup menu
		self.popup_menu = GmailPopupMenu.GmailPopupMenu( self)
		pynotify.init("gmail-notify")
		self.notify = pynotify.Notification(self.lang.get_string(21), "")
		self.notify.attach_to_status_icon(self.tray)

		self.init=1
		while gtk.events_pending():
			gtk.main_iteration(gtk.TRUE)
		# Attemp connection for first time
		if self.connect()==1:
			# Check mail for first time
			self.mail_check()

		self.maintimer=gtk.timeout_add(self.options['checkinterval'],self.mail_check)

	def connect(self):
		# If connecting, cancel connection
		if self.dont_connect==1:
			print "connection attemp suspended"
			return 0
		self.dont_connect=1
		print "connecting..."
		self.tray.set_tooltip(self.lang.get_string(13))
		while gtk.events_pending():
			gtk.main_iteration( gtk.TRUE)
		# Attemp connection
		try:
			self.connection=gmailatom.GmailAtom(self.options['gmailusername'],self.options['gmailpassword'])
			self.connection.refreshInfo()
			print "connection successful... continuing"
			self.tray.set_tooltip(self.lang.get_string(14))
			self.dont_connect=0
			return 1
		except:
			print "login failed, will retry"
			self.tray.set_tooltip(self.lang.get_string(15))
			self.notify.update(self.lang.get_string(15),self.lang.get_string(16))
			self.show_popup()
			self.dont_connect=0
			return 0

	def mail_check(self, event=None):
		# If checking, cancel mail check
		if self.mailcheck==1:
			print "self.mailcheck=1"
			return gtk.TRUE
		self.mailcheck=1
		print "----------"
		print "checking for new mail ("+time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())+")"
		while gtk.events_pending():
			gtk.main_iteration( gtk.TRUE)

		# Get new messages count
		attrs = self.has_new_messages()

		# If mail check was unsuccessful
		if attrs[0]==-1:
			self.mailcheck=0
			return gtk.TRUE

		# Update tray icon

		if attrs[1]>0:
			print str(attrs[1])+" new messages"
			sender = attrs[2]
			subject= attrs[3]
			snippet= attrs[4]
			self.notify.update(self.lang.get_string(17)+sender[0:24],shortenstring(subject,20)+"\n\n"+snippet+"...")
			self.show_popup()
		if attrs[0]>0:
			print str(attrs[0])+" unread messages"
			s = ' ' 
			if attrs[0]>1: s=self.lang.get_string(35)+" "
			self.tray.set_tooltip((self.lang.get_string(19))%{'u':attrs[0],'s':s})
			pixbuf = gtk.gdk.pixbuf_new_from_file( ICON2_PATH )
		else:
			print "no new messages"
			self.tray.set_tooltip(self.lang.get_string(18))
			pixbuf = gtk.gdk.pixbuf_new_from_file( ICON_PATH )
			self.notify.update(self.lang.get_string(21),self.lang.get_string(18))
		
		scaled_buf = pixbuf.scale_simple(24,24,gtk.gdk.INTERP_BILINEAR)
		self.tray.set_from_pixbuf(scaled_buf)
		self.unreadmsgcount=attrs[0]
		
		self.mailcheck=0

		return gtk.TRUE
	
	def has_new_messages( self):
		unreadmsgcount=0
		# Get total messages in inbox
		try:
			self.connection.refreshInfo()
			unreadmsgcount=self.connection.getUnreadMsgCount()
		except:
			# If an error ocurred, cancel mail check
			print "getUnreadMsgCount() failed, will try again soon"
			return (-1,)

		sender=''
		subject=''
		snippet=''
		finalsnippet=''
		if unreadmsgcount>0:
			# Get latest message data
			sender = self.connection.getMsgAuthorName(0)
			subject = self.connection.getMsgTitle(0)
			snippet = self.connection.getMsgSummary(0)
			if len(sender)>12: 
				finalsnippet=shortenstring(snippet,20)
			else:
				finalsnippet=shortenstring(snippet,40)
		# Really new messages? Or just repeating...
		newmsgcount=unreadmsgcount-self.unreadmsgcount
		self.unreadmsgcount=unreadmsgcount
		if unreadmsgcount>0:
			return (unreadmsgcount, newmsgcount, sender, subject, finalsnippet)
		else:
			return (unreadmsgcount,0, sender, subject, finalsnippet)

	def show_popup(self):
		try:
			self.notify.set_timeout(pynotify.EXPIRES_DEFAULT)
			self.notify.show()
		except gobject.GError: # ignore errors here
			pass

	def tray_icon_clicked(self,status_icon, button, activate_time):
		if button==3:
			self.popup_menu.show_menu(button, activate_time)
		else:
			self.show_popup()

	def exit(self, event):
		dialog = gtk.MessageDialog( None, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, self.lang.get_string(5))
		dialog.width, dialog.height = dialog.get_size()
		dialog.move( gtk.gdk.screen_width()/2-dialog.width/2, gtk.gdk.screen_height()/2-dialog.height/2)
		ret = dialog.run()
		if( ret==gtk.RESPONSE_YES):
			gtk.main_quit(0)
		dialog.destroy()

	def show_quota_info( self, event):
		print "Not available"
		#print "----------"
		#print "retrieving quota info"
		#while gtk.events_pending()!=0:
		#	gtk.main_iteration(gtk.TRUE)
		#try:
		#	usage=self.connection.getQuotaInfo()
		#except:
		#	if self.connect()==0:
		#		return
		#	else:
		#		usage=self.connection.getQuotaInfo()
		#self.label.set_markup("<span size='large' ><u><i>"+self.lang.get_string(6)+"</i></u></span>\n\n"+self.lang.get_string(24)%{'u':usage[0],'t':usage[1],'p':usage[2]})
		#self.show_popup()

	def update_config(self, event=None):
		# Kill all timers
		if self.init==1:gtk.timeout_remove(self.maintimer)
		# Run the configuration dialog
		self.configWindow.show()

		# Update timeout
		self.maintimer = gtk.timeout_add(self.options["checkinterval"], self.mail_check )

		# Update user/pass
		self.connection=gmailatom.GmailAtom(self.options["gmailusername"],self.options["gmailpassword"])
		self.connect()
		self.mail_check()

		# Update language
		self.lang=self.configWindow.get_lang()

		# Update popup menu
		self.popup_menu = GmailPopupMenu.GmailPopupMenu(self)

		return

	def main(self):
		gtk.main()

if __name__ == "__main__":
	warnings.filterwarnings( action="ignore", category=DeprecationWarning)
	gmailnotifier = GmailNotify()
	gmailnotifier.main()
