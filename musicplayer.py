import os, time
import curses
import subprocess
import signal
import threading
import sys
import random
import unicodedata

#ScrapePlayerDESKTOP
#dependencies:
#		sox (unix util)
#		curses

if len(sys.argv) >= 2:
	os.chdir(sys.argv[1])

#==============begin comparator

def istrcmp(a,b):
	return cmp(a.lower(),b.lower())
	
def songs_by_name_cmp(a,b):
	global INVERT_SONG
	return istrcmp(a['name'],b['name']) * INVERT_SONG
	
def songs_by_date_cmp(a,b):
	global INVERT_SONG
	return cmp(a['ftime'],b['ftime']) * INVERT_SONG
	
def folders_by_name_cmp(a,b):
	global INVERT_FOLDER
	return istrcmp(a.name,b.name) * INVERT_FOLDER
	
def folders_by_date_cmp(a,b):
	global INVERT_FOLDER
	return cmp(a.cached_date,b.cached_date) * INVERT_FOLDER
	
SONG_COMPARATOR = songs_by_name_cmp
FOLDER_COMPARATOR = folders_by_name_cmp
INVERT_SONG = 1
INVERT_FOLDER = 1

LIST_ALL = False
FILTER = ""

#==============begin class definitions

class FolderNode:
	all_nodes = []
	@classmethod
	def set_all_dirty(cls):
		for node in cls.all_nodes:
			node.dirty_songs = True
			node.dirty_folders = True

	def __init__(self, name):
		self.name = name
		self.songs = {}
		self.subfolders = {}
		self.fulldir = "/"
		self.parent = None
		self.cached_date = 0
		self.allsongs = {}
		
		self.dirty_songs = True
		self.dirty_folders = True
		self.cached_songs = None
		self.cached_folders = None
		FolderNode.all_nodes.append(self)
		
	def get_songs(self):
		global LIST_ALL
		if LIST_ALL:
			return self.allsongs
		else:
			return self.songs
	
	def time(self):
		if (self.cached_date == 0):
			self.cached_date = os.path.getmtime(self.fulldir)
		return self.cached_date
		
	def add_song(self, songdata): 
		self.songs[songdata['name']] = songdata
		
	def add_subfolder(self, name):
		self.subfolders[name] = FolderNode(name)
		self.subfolders[name].parent = self
		return self.subfolders[name]
		
	def get_songnames(self):
		global SONG_COMPARATOR, FILTER
		if self.dirty_songs:
			use = self.get_songs()
			rtv = [use[song] for song in use]
			rtv.sort(SONG_COMPARATOR)
			rtv = [song['name'] for song in rtv if (FILTER.lower() in song['name'].lower())]
			self.cached_songs = rtv
			self.dirty_songs = False
		
		return self.cached_songs
		
	def get_foldernames(self):
		global FOLDER_COMPARATOR
		if self.dirty_folders:
			rtv = [self.subfolders[folder] for folder in self.subfolders]
			rtv.sort(FOLDER_COMPARATOR)
			rtv = [folder.name for folder in rtv]
			self.cached_folders = rtv
			self.dirty_folders = False
		return self.cached_folders
		
class Range2d:
	def __init__(self,xmin,xmax,ymin,ymax):
		self.xmin = xmin
		self.xmax = xmax
		self.ymin = ymin
		self.ymax = ymax
		
def str_safe_convert(msg):
	sbuf = ""
	for i in range(0,len(msg)):
		try:
			sbuf = sbuf + remove_accents(msg[i])
		except UnicodeEncodeError:
			sbuf = sbuf + "?"
		except KeyError:
			sbuf = sbuf + "?"
	return sbuf

def remove_accents(data):
    return ''.join(x for x in unicodedata.normalize('NFKD', data) if x in string.ascii_letters).lower()
		
#=============begin folder crawling code
		
file_types = ['.mp3','.flac','.wav','.ogg','.aiff','.m4a']
file_tree = FolderNode("/")
file_tree.fulldir = os.getcwd()
current_folder = file_tree

def r_crawldirs():
	global current_folder
	
	ldirs = [f for f in os.listdir('.') if os.path.isdir(f)]
	fdir = [f for f in os.listdir('.') if os.path.isfile(f)]
	cwd = os.getcwd()
	
	for file in fdir:
		name,ext = os.path.splitext(file)
		if not ext in file_types:
			continue
		ftime = os.path.getmtime(file)
		current_folder.add_song({
			'file':os.path.join(cwd,file),
			'name':name.decode('utf-8'),
			'ext':ext,
			'ftime':ftime
		})
	for folder in ldirs:
		try:
			pre_dir = os.getcwd()
			os.chdir(folder)
			parent_folder = current_folder
			current_folder = current_folder.add_subfolder(folder)
			current_folder.fulldir = os.path.join(cwd,folder)
			current_folder.time() #gotta set that cached time
			r_crawldirs()
			current_folder = parent_folder
			os.chdir(pre_dir)
		except:
			os.chdir(cwd)
			
r_crawldirs()

def dict_addto(dto,dfrom):
	for key in dfrom:
		dto[key] = dfrom[key]
	
def fill_allsongs(cur):
	parent = cur
	dict_addto(cur.allsongs,cur.songs)
	for childname in cur.subfolders:
		childsongs = fill_allsongs(cur.subfolders[childname])
		dict_addto(cur.allsongs,childsongs)
	return cur.allsongs
	
fill_allsongs(current_folder)

#========== BEGIN NCURSES CODE

def nc_begin():
	stdscr = curses.initscr()
	curses.noecho()
	curses.cbreak()
	stdscr.keypad(1)
	return stdscr

STDSCR = nc_begin()
HEI,WID = STDSCR.getmaxyx()
HEI = HEI-1
WID = WID-1

def nc_end():
	global STDSCR
	curses.nocbreak(); STDSCR.keypad(0); curses.echo()
	curses.endwin()

def nc_drawat(x,y,char):
	global STDSCR,WID,HEI
	if x < WID and y < HEI:
		try:
			STDSCR.addch(y,x,char)
		except:
			HEI,WID = STDSCR.getmaxyx()

def nc_drawstringat(x,y,msg): 
	global STDSCR,WID,HEI
	if y <= HEI:
		msg = msg[0:( len(msg)-(x+len(msg)-WID) if x+len(msg)-WID > 0 else len(msg) )]
		try:
			STDSCR.addstr(y,x,msg)
		except UnicodeEncodeError:
			for i in range(0,len(msg)):
				try:
					STDSCR.addstr(y,x+i,msg[i])
				except UnicodeEncodeError:
					STDSCR.addstr(y,x+i,"?")
		
		
def get_folderbox_range():
	global WID,HEI
	return Range2d(1,WID-1,3,int(HEI*0.43))
	
def get_songbox_range():
	global WID,HEI
	return Range2d(1,WID-1,int(HEI*0.43)+2,int(HEI*0.8))
		
def draw_ui():
	global WID,current_folder,current_mode
	nc_drawstringat(0,0,"ScrapePlayerDESKTOP 0.2 powered by SoX and ncurses (NOW U CAN RESIZE IT)")
	
	folders_max = int(len(current_folder.get_foldernames())/(get_folderbox_internal_height()))+1
	if len(current_folder.get_foldernames()) % get_folderbox_internal_height() == 0:
		folders_max = folders_max - 1
	
	nc_drawstringat(0,2,"%sFolders(Page %s) %s"%(
		">>>" if current_mode == Mode.FOLDERS else "   ",
		"%d/%d"%(folder_offset+1,folders_max),
		current_folder.fulldir
	))
	
	
	folderbox_range = get_folderbox_range()
	nc_drawstringat(folderbox_range.xmax-25,folderbox_range.ymin-1,"Last Modified:")
	for y in range(folderbox_range.ymin,folderbox_range.ymax):
		for x in range(folderbox_range.xmin,folderbox_range.xmax):
			nc_drawat(x,y,'+') if y == folderbox_range.ymin or y == folderbox_range.ymax-1 else 0
			nc_drawat(x,y,'+') if x == folderbox_range.xmin or x == folderbox_range.xmax-1 else 0
	songbox_range = get_songbox_range()

	songs_max = int(len(current_folder.get_songnames())/ (get_songbox_internal_height())) + 1
	if len(current_folder.get_songnames()) % get_songbox_internal_height() == 0:
		songs_max = songs_max - 1

	nc_drawstringat(0,songbox_range.ymin-1,"%sSongs(Page %s)"%(
		">>>" if current_mode == Mode.SONGS else "   ",
		"%d/%d"%(
			songs_offset+1,
			songs_max
		)
	))

	nc_drawstringat(songbox_range.xmax-25,songbox_range.ymin-1,"Last Modified:")
	for y in range(songbox_range.ymin,songbox_range.ymax):
		for x in range(songbox_range.xmin,songbox_range.xmax): 
			nc_drawat(x,y,'+') if y == songbox_range.ymin or y == songbox_range.ymax-1 else 0
			nc_drawat(x,y,'+') if x == songbox_range.xmin or x == songbox_range.xmax-1 else 0
	nc_drawstringat(0,HEI-6,"(Q)uit (T)ab (Arrow keys)move (Z/X)Page up/down (P)lay/Pause")
	nc_drawstringat(0,HEI-5,"(o)Sort by (I)nvert (V)olume (F)ilter by (L)ist all/folder (S)huffle")
	nc_drawstringat(0,HEI-4,"=======MESSAGES:=======")
	
def draw_folders():
	global WID,HEI,current_folder,debug_output, folder_localindex, folder_offset
	folderbox_range = get_folderbox_range()
	folders = current_folder.get_foldernames()
	i = folder_offset * get_folderbox_internal_height()
	for y in range(folderbox_range.ymin+1,folderbox_range.ymax-1):
		if (i >= len(folders)):
			break
		nc_drawstringat(folderbox_range.xmax-26,y,time.ctime(current_folder.subfolders[folders[i]].time()))
		nc_drawstringat(folderbox_range.xmin+2,y,folders[i])
		nc_drawstringat(folderbox_range.xmin+1,y,">") if i == folder_localindex + (folder_offset * get_folderbox_internal_height()) else nc_drawstringat(folderbox_range.xmin+1,y," ")  
		i = i + 1
		
def draw_songs():
	global WID,HEI,current_folder,debug_output, songs_localindex, songs_offset
	songbox_range = get_songbox_range()
	songs = current_folder.get_songnames()
	i = songs_offset * get_songbox_internal_height()
	for y in range(songbox_range.ymin+1,songbox_range.ymax-1):
		if (i >= len(songs)):
			break
		nc_drawstringat(songbox_range.xmax-26,y,time.ctime(current_folder.get_songs()[songs[i]]['ftime']))
		nc_drawstringat(songbox_range.xmin+2,y,songs[i])
		nc_drawstringat(songbox_range.xmin+1,y,">") if i == songs_localindex + (songs_offset * get_songbox_internal_height()) else nc_drawstringat(songbox_range.xmin+1,y," ") 
		i = i + 1
		
def clear_screen():
	global WID,HEI
	for y in range(0,HEI):
		for x in range(0,WID):
			nc_drawat(x,y," ")
		
def get_songbox_internal_height():
	songbox_range = get_songbox_range()
	return (songbox_range.ymax-1) - (songbox_range.ymin+1)
	
def get_folderbox_internal_height():
	folderbox_range = get_folderbox_range()
	return (folderbox_range.ymax-1) - (folderbox_range.ymin+1)


#===========BEGIN input loop

def update_screen():
	clear_screen()
	draw_ui()
	nc_drawstringat(0,HEI-3," "*WID)
	draw_folders()
	draw_songs()
	nc_drawstringat(0,HEI-3,debug_output)
	nc_drawstringat(0,HEI-2,debug_output2)
	STDSCR.refresh()

def get_actual_songindex():
	return songs_localindex + songs_offset * get_songbox_internal_height()

def get_actual_folderindex():
	return folder_localindex + folder_offset * get_folderbox_internal_height()

def reset_folder_and_song_indexes():
	global folder_localindex,folder_offset,songs_localindex,songs_offset
	folder_localindex = 0
	folder_offset = 0
	songs_localindex = 0
	songs_offset = 0
	
def song_finished():
	global songs_localindex, songs_offset, current_folder, currently_playing_poller, currently_playing, is_paused, folder_offset
	global SHUFFLE
	
	currently_playing = None
	currently_playing_poller = None
	
	use_height = len(current_folder.get_songnames()) % get_songbox_internal_height()
	if use_height == 0 and len(current_folder.get_songnames()) != 0:
		use_height = get_songbox_internal_height()
	elif (get_songbox_internal_height() + songs_offset * get_songbox_internal_height()) < len(current_folder.get_songnames()):
		use_height = get_songbox_internal_height()
		
	ins = songs_localindex
	
	if SHUFFLE:
		songs_localindex = random.randint(0,get_songbox_internal_height()) % use_height
		songs_offset = random.randint(0,int(len(current_folder.get_songnames())/get_songbox_internal_height()))
		
	else:
		songs_localindex = songs_localindex + 1
		
		
	if (songs_localindex >= use_height):
		songs_localindex = 0
		songs_offset = songs_offset+1
		
	songindex = get_actual_songindex()
	if (songindex >= len(current_folder.get_songnames())):
		songs_offset = 0

	songindex = get_actual_songindex()
	if (songindex < len(current_folder.get_songnames())):
		songname = current_folder.get_songnames()[songindex]
		songdata = current_folder.get_songs()[songname]
		is_paused = False
		play_song(songdata["file"])
		update_screen()
		
	else:
		nc_drawstringat(0,HEI-2,"song_finished but cannot next")
		STDSCR.refresh()
			
	
	
def play_song(file):
	global currently_playing, currently_playing_poller,currently_playing_key,debug_output,VOLUME
	cmd = """play --volume %f '%s' -q -V0"""%(VOLUME,file.replace("'","\'\\\'\'"))
	currently_playing = subprocess.Popen(cmd,shell=True)
	currently_playing_poller = ProcessPoller(currently_playing)
	currently_playing_poller.start()
	currently_playing_key = file
	debug_output = cmd
	
class Mode:
	FOLDERS = 0
	SONGS = 1
	
class ProcessPoller(threading.Thread):
	def __init__(self, target):
		threading.Thread.__init__(self)
		self.target = target
		self.kill = False
		
	def run(self):
		self.target.wait()
		if not self.kill:
			self.kill = True
			song_finished()
			
class InputMode:
	VOLUME = 0
	FILTER = 1
	
VOLUME = 1
SHUFFLE = False
current_folder = file_tree
debug_output = ""
debug_output2 = ""
current_mode = Mode.FOLDERS
folder_localindex = 0
folder_offset = 0
songs_localindex = 0
songs_offset = 0

currently_playing = None
currently_playing_poller = None
currently_playing_key = ""
is_paused = False

cur_input_mode = None
input_buffer = ""
	
try:
	INPUT = ''
	while True:
		HEI,WID = STDSCR.getmaxyx()
		if cur_input_mode != None:
			if INPUT == curses.KEY_ENTER or INPUT == 10:
				debug_output = ""
				debug_output2 = ""
				if cur_input_mode == InputMode.VOLUME:
					try:
						val = float(input_buffer)
						VOLUME = val
					except:
						debug_output = "invalid volume"
				
				elif cur_input_mode == InputMode.FILTER:
					FILTER = input_buffer
					debug_output = """filtering on '%s'"""%(FILTER)
					FolderNode.set_all_dirty()
					reset_folder_and_song_indexes()
				
				cur_input_mode = None
			
			else:
				input_buffer += chr(INPUT)
				debug_output2 = input_buffer
			
			
		else:
		
			if INPUT == ord('v'):
				cur_input_mode = InputMode.VOLUME
				debug_output = "input volume:"
				input_buffer = ""
				
			elif INPUT == ord('n'):
				if currently_playing != None:
					currently_playing.send_signal(signal.SIGKILL)
				
			elif INPUT == ord('f'): 
				cur_input_mode = InputMode.FILTER
				debug_output = "filter name:"
				input_buffer = ""
				
			elif INPUT == ord('s'):
				SHUFFLE = not SHUFFLE
				debug_output = "shuffle: %d"%(SHUFFLE)
			
			elif INPUT == ord('q'):
				break
				
			elif INPUT == ord('l'):
				LIST_ALL = not LIST_ALL
				reset_folder_and_song_indexes()
				debug_output = "LIST_ALL:%d"%LIST_ALL
				FolderNode.set_all_dirty()
				
			elif INPUT == ord('t'):
				current_mode = (current_mode+1)%2
				FolderNode.set_all_dirty()
	
			elif INPUT == ord('i'):
				FolderNode.set_all_dirty()
				if current_mode == Mode.FOLDERS:
					INVERT_FOLDER = -1 if INVERT_FOLDER == 1 else 1
					reset_folder_and_song_indexes()
					debug_output = "invert folder:%d"%INVERT_FOLDER
								
				elif current_mode == Mode.SONGS:
					INVERT_SONG = -1 if INVERT_SONG == 1 else 1
					reset_folder_and_song_indexes()
					debug_output = "invert song:%d"%INVERT_SONG
					
			elif INPUT == ord('o'):
				FolderNode.set_all_dirty()
				if current_mode == Mode.SONGS:
					SONG_COMPARATOR = songs_by_name_cmp if SONG_COMPARATOR == songs_by_date_cmp else songs_by_date_cmp
					debug_output = "song sorted by %s"%("date" if SONG_COMPARATOR == songs_by_date_cmp else "name")
					reset_folder_and_song_indexes()
				
				elif current_mode == Mode.FOLDERS:
					FOLDER_COMPARATOR = folders_by_name_cmp if FOLDER_COMPARATOR == folders_by_date_cmp else folders_by_date_cmp
					debug_output = "folders sorted by %s"%("date" if FOLDER_COMPARATOR == folders_by_date_cmp else "name")
					reset_folder_and_song_indexes()
				
			
			elif INPUT == curses.KEY_LEFT:
				if current_mode == Mode.FOLDERS:
					reset_folder_and_song_indexes()
					if (current_folder.parent != None):
						current_folder = current_folder.parent
					else:
						debug_output = "at root"
					
				
			elif INPUT == curses.KEY_RIGHT:
				if current_mode == Mode.FOLDERS:
					if len(current_folder.get_foldernames()) > 0:
						target_folder = current_folder.get_foldernames()[get_actual_folderindex()]
						if target_folder in current_folder.subfolders:
							current_folder = current_folder.subfolders[target_folder]
							reset_folder_and_song_indexes()
					else:
						debug_output = "empty folder" 
				
			elif INPUT == curses.KEY_UP:
				if current_mode == Mode.FOLDERS:
					folder_localindex = folder_localindex - 1
					if folder_localindex < 0:
						folder_localindex = min(len(current_folder.get_foldernames())-1-folder_offset * get_folderbox_internal_height(),get_folderbox_internal_height()-1)
			
					
				elif current_mode == Mode.SONGS:
					songs_localindex = songs_localindex - 1
					if songs_localindex < 0:
						songs_localindex = min(len(current_folder.get_songnames())-1-songs_offset * get_songbox_internal_height(),get_songbox_internal_height()-1)
			
			elif INPUT == curses.KEY_DOWN:
				if current_mode == Mode.FOLDERS:
					folder_localindex = folder_localindex + 1
					if (folder_localindex + folder_offset * get_folderbox_internal_height()) > min(len(current_folder.get_foldernames())-1,get_folderbox_internal_height()*(folder_offset+1)-1):
						folder_localindex = 0
					
				elif current_mode == Mode.SONGS:
					songs_localindex = songs_localindex + 1
					if (songs_localindex + songs_offset * get_songbox_internal_height()) > min(len(current_folder.get_songnames())-1,get_songbox_internal_height()*(songs_offset+1)-1):
						songs_localindex = 0
					
			
			elif INPUT == ord('z'):
				if current_mode == Mode.FOLDERS:
					folder_localindex = 0
					if folder_offset > 0:
						folder_offset = folder_offset - 1
					else:
						while (folder_offset+1) * (get_folderbox_internal_height()) < len(current_folder.get_foldernames()):
							folder_offset = folder_offset+1
					
				elif current_mode == Mode.SONGS:
					songs_localindex = 0
					if songs_offset > 0:
						songs_offset = songs_offset - 1
					else:
						while (songs_offset+1) * (get_songbox_internal_height()) < len(current_folder.get_songnames()):
							songs_offset = songs_offset+1
					
			elif INPUT == ord('x'):
				if current_mode == Mode.FOLDERS:
					folder_localindex = 0
					folder_range = get_folderbox_range()
					folder_offset = folder_offset + 1 if (folder_offset+1) * (get_folderbox_internal_height()) < len(current_folder.get_foldernames()) else 0
					
					
				elif current_mode == Mode.SONGS:
					songs_localindex = 0
					songbox_range = get_songbox_range()
					songs_offset = songs_offset + 1 if (songs_offset+1) * (get_songbox_internal_height()) < len(current_folder.get_songnames()) else 0
					
			elif INPUT == ord('p'):
				if current_mode == Mode.SONGS:
					if len(current_folder.get_songnames()) > 0:
						songname = current_folder.get_songnames()[get_actual_songindex()]
						songdata = current_folder.get_songs()[songname]
			
						if currently_playing == None:
							is_paused = False
							play_song(songdata["file"])
				
						else:
							if songdata["file"] == currently_playing_key:
								if is_paused:
									currently_playing.send_signal(signal.SIGCONT)
									is_paused = False
									debug_output = "now playing: '%s'"%(songdata["file"])
							
								else:
									currently_playing.send_signal(signal.SIGSTOP)
									is_paused = True
									debug_output = "paused: '%s'"%(songdata["file"])
						
							else:
								is_paused = False
								currently_playing_poller.kill = True
								currently_playing.send_signal(signal.SIGTERM)
								play_song(songdata["file"])

		
		update_screen()
		INPUT = STDSCR.getch()
except:
	nc_end()
	if currently_playing != None:
		currently_playing_poller.kill = True
		currently_playing.send_signal(signal.SIGKILL)
	raise
finally:
	if currently_playing != None:
		currently_playing_poller.kill = True
		currently_playing.send_signal(signal.SIGKILL)
	nc_end()
os.system("killall play")
exit()
