#! /usr/bin/env python
# -*- coding: utf-8 -*-

#modules in standard library
import requests
import sys, os, re
import time
from time import strftime
import argparse
from bs4 import BeautifulSoup
import json
import traceback
from requests.exceptions import Timeout

# external modules
from config import PLUS, WARNING, INFO, LESS, LINE, FORBI, BACK, EXCL
try:
    from Queue import Queue
except:
    import queue as Queue
from threading import Thread
import threading
from fake_useragent import UserAgent
import wafw00f
try:
    from tools.Sublist3r import sublist3r
except Exception:
    if sys.version > '3':
        print("\n{}subbrute doesn't work with this script on py3 version for the moment sorry".format(INFO))
    pass    
from report.creat_report import create_report
#from report.creat_report_test import create_report_test
from modules.detect_waf import verify_waf
from modules.mini_scans import mini_scans
from modules.parsing_html import parsing_html
from modules.detect_scan import detect_scans
from modules.bypass_waf import bypass_waf

def banner():
    print("""
  _    _                _     _____                 
 | |  | |              | |   / ____|                
 | |__| | __ ___      _| | _| (___   ___ __ _ _ __  
 |  __  |/ _` \ \ /\ / / |/ /\___ \ / __/ _` | '_ \ 
 | |  | | (_| |\ V  V /|   < ____) | (_| (_| | | | |
 |_|  |_|\__,_| \_/\_/ |_|\_\_____/ \___\__,_|_| |_|
                                                    

https://github.com/c0dejump/HawkScan
\033[35mv1.2 \033[0m
___________________________________________________________________
    """)

try:
    enclosure_queue = Queue()
except:
    enclosure_queue = Queue.Queue()

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

rec_list = []
#list to append url and then recursif scan

req_p = u""
#for exclude option

stat = 0


class ThreadManager:
    """
    Class ThreadManager:
        To manage threads (add_thread())
        To stop thread (stop_thread())
    """
    workers = []

    errors_score = 0

    lock = threading.Lock()

    def __init__(self, queue):
        self.queue = queue
 
    def add_thread(self, i, threads, manager):
        """
        add thread from function definded_thread()
        """
        #print(self.workers[0])
        t_event = threading.Event()
        worker = threading.Thread(target=thread_wrapper, args=(i, self.queue, threads, manager, t_event))
        worker.setDaemon(True)
        worker.start()
        self.workers.append((worker, t_event))

    def stop_thread(self):
        t, e = self.workers[0]
        e = e.set() # put event to set True for stop thread
        del self.workers[0]

    def error_check(self):
        #TODO
        with lock:
            errors_score += 1
            return errors_score

def auto_update():
    """
    auto_update: for update the tool
    """
    if update:
        updt = 0
        print("{}Checking update...".format(INFO))
        os.system("git pull origin master > /dev/null 2>&1 > git_status.txt")
        with open("git_status.txt", "r") as gs:
            for s in gs:
                if "Already up to date" not in s:
                    updt = 1
        if updt == 1:
            print("{}A new version was be donwload\n".format(INFO))
            os.system("rm -rf git_status.txt")
        else:
            print("{}Nothing update found".format(INFO))
            os.system("rm -rf git_status.txt")


def status(stat, directory, u_agent, thread):
    """
    Status:
     - Get response status of the website (200, 302, 404...).
     - Check if a backup exist before to start the scan.
     If exist it restart scan from to the last line of backup.
    """
    check_b = check_backup(directory)
    #check backup before start scan
    if check_b == True:
        with open(directory + "/backup.txt", "r") as word:
            for ligne in word.readlines():
                print("{}{}{}".format(BACK, url, ligne.replace("\n","")))
                lignes = ligne.split("\n")
                #take the last line in file
                last_line = lignes[-2]
            with open(wordlist, "r") as f:
                for nLine, line in enumerate(f):
                    line = line.replace("\n","")
                    if line == last_line:
                        print(LINE)
                        forced = False
                        check_words(url, wordlist, directory, u_agent, thread, forced, nLine)
    elif check_b == False:
        os.remove(directory + "/backup.txt")
        print("restarting scan...")
        print(LINE)
    if stat == 200:
        check_words(url, wordlist, directory, u_agent, thread)
    elif stat == 301:
        try:
            follow = raw_input("{} 301 Moved Permanently\nDo you want follow redirection ? [y/N]".format(PLUS))
            print("")
        except:
            follow = input("{} 301 Moved Permanently\nDo you want follow redirection ? [y/N]".format(PLUS))
            print("")
        stat = 301 if follow == "y" or follow == "Y" else 0
        check_words(url, wordlist, directory, u_agent, thread)
    elif stat == 302:
        try:
            follow = raw_input("{} 302 Moved Temporarily\nDo you want follow redirection ? [y/N]".format(PLUS))
            print("")
        except:
            follow = input("{} 302 Moved Temporarily\nDo you want follow redirection ? [y/N]".format(PLUS))
            print("")
        stat = 302 if follow == "y" or follow == "Y" else 0
        check_words(url, wordlist, directory, u_agent, thread)
    elif stat == 304:
        pass
    elif stat == 404:
        try:
            not_found = raw_input("{} not found/ forced ? [y/N]: ".format(LESS))
        except:
            not_found = input("{} not found/ forced ? [y/N]: ".format(LESS))
        if not_found == "y" or not_found == "Y":
            forced = True
            check_words(url, wordlist, directory, u_agent, thread, forced)
        else:
            sys.exit()
    elif stat == 403:
        try:
            fht = raw_input(FORBI + " forbidden/ forced ? [y/N]: ")
        except:
            fht = input(FORBI + " forbidden/ forced ? [y/N]: ")
        if fht == "y" or fht == "Y":
            forced = True
            check_words(url, wordlist, directory, u_agent, thread, forced)
        else:
            sys.exit()
    else:
        try:
            not_found = raw_input("{} not found/ forced ? [y/N]: ".format(LESS))
        except:
            not_found = input("{} not found/ forced ? [y/N]: ".format(LESS))
        if not_found == "y" or not_found == "Y":
            forced = True
            check_words(url, wordlist, directory, u_agent, thread, forced)
        else:
            sys.exit()


def subdomain(subdomains):
    """
    Subdomains:
    Check subdomains with the option -s (-s google.fr)
    script use sublit3r to scan subdomain (it's a basic scan)
    """
    print("search subdomains:\n")
    sub_file = "sublist/" + subdomains + ".txt"
    sub = sublist3r.main(subdomains, 40, sub_file, ports=None, silent=False, verbose=False, enable_bruteforce=False, engines=None)
    print(LINE)
    time.sleep(2)


def detect_waf(url, directory, thread):
    """
    WAF:
    Detect if the website use a WAF with tools "wafw00f"
    """
    detect = False
    message = ""
    os.system("wafw00f {} > {}/waf.txt".format(url, directory))
    with open(directory + "/waf.txt", "r+") as waf:
        for w in waf:
            if "behind" in w:
                detect = True
                message = w
            else:
                pass
        print(INFO + "WAF")
        print(LINE)
        if detect == True:
            print("  {}{}".format(WARNING, message))
            if thread >= 20:
                try:
                    confirm_thread = raw_input("{}This website have a waf are you sure to use {} threads ? [y:n] ".format(WARNING, thread))
                except:
                    confirm_thread = input("{}This website have a waf are you sure to use {} threads ? [y:n] ".format(WARNING, thread))
                if confirm_thread == "y" or confirm_thread == "Y":
                    pass
                else:
                    try:
                        enter_thread = raw_input("{}Enter the number of threads: ".format(INFO))
                    except:
                        enter_thread = input("{}Enter the number of threads: ".format(INFO))
                    if int(enter_thread) > 0:
                        print(LINE)
                        return int(enter_thread)
                    else:
                        print("If you enter 0 that's will doesn't work :)")
                        sys.exit()
        else:
            print("\t{}This website dos not use WAF".format(LESS))
            print(LINE)

def check_backup(directory):
    """Check if a backup file exist from function 'Status' """
    if os.path.exists(directory + "/backup.txt"):
        try:
            bp = raw_input("A backup file exist, do you want to continue or restart ? [c:r]: ")
        except:
            bp = input("A backup file exist, do you want to continue or restart ? [c:r]: ")
        if bp == 'C' or bp == 'c':
            print("restart from last save in backup.txt ...")
            print(LINE)
            return True
        else:
            print(LINE)
            return False
    else:
        pass


def create_backup(res, directory, forbi):
    """Create backup file"""
    with open(directory + "/backup.txt", "a+") as words:
        #delete url to keep just file or dir
        anti_sl = res.split("/")
        rep = anti_sl[3:]
        result = str(rep)
        result = result.replace("['","").replace("']","").replace("',", "/").replace(" '","")
        words.write(result + "\n")


def dl(res, req, directory):
    """ Download files and calcul size """
    soup = BeautifulSoup(req.text, "html.parser")
    extensions = ['.txt', '.html', '.jsp', '.xml', '.php', '.aspx', '.zip', '.old', '.bak', '.sql', '.js', '.asp', '.ini', '.rar', '.dat', '.log', '.backup', '.dll', '.save', '.BAK', '.inc', '.php?-s']
    d_files = directory + "/files/"
    if not os.path.exists(d_files):
        os.makedirs(d_files)
    anti_sl = res.split("/")
    rep = anti_sl[3:]
    result = rep[-1]
    p_file = d_files + result
    texte = req.text
    for exts in extensions:
        if exts in result:
            with open(p_file, 'w+') as fichier:
                fichier.write(str(soup))
            # get size of file (in bytes)
            size_bytes = os.path.getsize(p_file)
            return size_bytes


def outpt(directory, res, stats):
    """
    outpt:
    Output to scan
    """
    if output:
        with open(output + "/scan.txt", "a+") as op:
            if stats == 403:
                op.write(str("[x] " + res + " Forbidden\n"))
            else:
                op.write(str("[+] " + res + "\n"))
    else:
        with open(directory + "/scan.txt", "a+") as op:
            if stats == 403:
                op.write(str("[x] " + res + " Forbidden\n"))
            elif stats == 301:
                op.write(str("[+] " + res + " 301\n"))
            elif stats == 302:
                op.write(str("[+] " + res + " 302\n"))
            elif stats == 401:
                op.write(str("[-] " + res + " 401\n"))
            elif stats == 400:
                op.write(str("[!] " + res + " 400\n"))
            elif stats == 500:
                op.write(str("[!] " + res + " 500\n"))
            else:
                op.write(str("[+] " + res + "\n"))


def check_exclude_page(req, res, directory, forbi, HOUR, size_bytes=False):
    """
    Check_exclude_page: 
    If scan blog, or social network etc.. you can activate this option to pass profil/false positive pages or response status code.
    for use this option you do defined a profil/false positive page base, ex: 
        --exclude url.com/profil/codejump
        --exclude 500
    """
    if redirect or stat == 301 or stat == 302:
        req = requests.get(req.url, verify=False)

    if type(exclude) == int:
        if req.status_code == req_p:
            pass
        else:
            return True
    else:
        words = req_p
        for w in words.split("\n"):
            if w in req.text:
                scoring += 1
            else:
                pass
        len_wd = [lines for lines in words.split("\n")] #to avoid to do line per line
        perc = round(100 * float(scoring) / len(len_wd)) #to do a percentage for check look like page
        #print(req.text)
        #print(perc) #DEBUG percentage
        if perc >= 80:
            pass
        elif perc > 50 and perc < 80:
            print("{} {} {} Potential exclude page {}%".format(HOUR, EXCL, res, perc))
        else:
            if size_bytes:
                print("{} {} {} ({} bytes)".format(HOUR, PLUS, res, size_bytes))
            else:
                print("{} {} {}".format(HOUR, PLUS, res))
            #check backup
            create_backup(res, directory, forbi)
            #output scan.txt
            outpt(directory, res, stats=0)
            if res[-1] == "/" and recur:
                if ".git" in res:
                    pass
                else:
                    spl = res.split("/")[3:]
                    result = "/".join(spl)
                    rec_list.append(result)
                    outpt(directory, res, stats=0)


def file_backup(s, res, directory, forbi, HOUR):
    """
    file_backup:
    During the scan, check if a backup file or dir exist.
    """
    size_check = 0

    ext_b = ['.key', '.log', '.ini', '.env', '.dat', '.conf', '.config', '.cgi', '.bok', '.bkf', '.action', 
    '.save', '.old', '.NEW', '.backup', '.BAK', '.bak', '.bak1', '.zip', '.rar', '~', '_old', '_backup', '_bak', 
    '/..%3B/', '/%20../', "?stats=1", "authorize/", ".json", ".bkp", ".wml", ".xml", ".xsd", ".yml"]
    d_files = directory + "/files/"
    for exton in ext_b:
        res_b = res + exton
        #print(res_b)
        anti_sl = res_b.split("/")
        rep = anti_sl[3:]
        result = rep[-1]
        r_files = d_files + result
        if ts:
            time.sleep(ts)
        if cookie_auth:
            req_b = s.get(res_b, allow_redirects=False, verify=False, cookies=cookie_auth)
        else:
            if redirect:
                req_check = s.get(res_b, allow_redirects=True, verify=False)
                req_b = s.get(req_check.url, verify=False)
            else:
                req_b = s.get(res_b, allow_redirects=False, verify=False)
        soup = BeautifulSoup(req_b.text, "html.parser")
        req_b_status = req_b.status_code
        if req_b_status == 200:
            with open(r_files+"-file.txt", 'w+') as fichier_bak:
                fichier_bak.write(str(soup))
            size_bytes = os.path.getsize(r_files+"-file.txt")
            ranges = range(size_check - 30, size_check + 30) if size_check < 100000 else range(size_check - 1000, size_check + 1000)
            if size_bytes == size_check or size_bytes in ranges:
                #if the number of bytes of the page equal to size_check variable and not bigger than size_check +5 and not smaller than size_check -5
                pass
            elif size_bytes != size_check:
                if exclude:
                    cep = check_exclude_page(req_b, res_b, directory, forbi, HOUR, size_bytes)
                    if cep:
                        print("{} {} {} ({} bytes)".format(HOUR, PLUS, res_b, size_bytes))
                else:
                    print("{} {} {} ({} bytes)".format(HOUR, PLUS, res_b, size_bytes))
                outpt(directory, res_b, 200)
                size_check = size_bytes
            else:
                if exclude:
                    cep = check_exclude_page(req_b, res_b, directory, forbi, HOUR)
                    if cep:
                       print("{} {} {}".format(HOUR, PLUS, res_b)) 
                else:
                    print("{} {} {}".format(HOUR, PLUS, res_b))
                    outpt(directory, res_b, 200)
        elif req_b_status == 404:
            pass
        elif req_b_status == 500:
            pass
        elif req_b_status == 401:
            pass
        elif req_b_status == 301 or req_b_status == 302 or req_b_status == 303:
            if redirect:
                print("{} {} {} => {}".format(HOUR, LESS, res_b, req_check.url))
        elif req_b_status == 403:
            pass
            #print("{}{}{}".format(HOUR, FORBI, res_b))
        elif req_b.status_code == 429:
            pass
        elif req_b_status == 406:
            pass
        elif req_b_status == 503 or req_b_status == 400:
            pass
        else:
            print("{}{} {}".format(HOUR, res_b, req_b.status_code))


def hidden_dir(res, user_agent, directory, forbi, HOUR):
    """
    hidden_dir:
    Like the function 'file_backup' but check if the type backup dir like '~articles/' exist.
    """
    pars = res.split("/")
    hidd_d = "{}~{}/".format(url, pars[3])
    hidd_f = "{}~{}".format(url, pars[3])
    if cookie_auth:
        req_d = requests.get(hidd_d, headers=user_agent, allow_redirects=False, verify=False, timeout=10, cookies=cookie_auth)
        req_f = requests.get(hidd_f, headers=user_agent, allow_redirects=False, verify=False, timeout=10, cookies=cookie_auth)
    else:
        req_d = requests.get(hidd_d, headers=user_agent, allow_redirects=False, verify=False, timeout=10)
        req_f = requests.get(hidd_f, headers=user_agent, allow_redirects=False, verify=False, timeout=10)
    sk_d = req_d.status_code
    sk_f = req_f.status_code
    if sk_d == 200:
        if exclude:
            cep = check_exclude_page(req_d, res, directory, forbi, HOUR)
            if cep:
                print("{} {} {}".format(HOUR, PLUS, hidd_d))
        else:
            print("{} {} {}".format(HOUR, PLUS, hidd_d))
            outpt(directory, hidd_d, 200)
    elif sk_f == 200:
        if exclude:
            cep = check_exclude_page(req_f, res, directory, forbi, HOUR)
            if cep:
                print("{} {} {}".format(HOUR, PLUS, hidd_f))
        else:
            print("{} {} {}".format(HOUR, PLUS, hidd_f))
            outpt(directory, hidd_f, 200)


def scan_error(directory, forbi):
    """
    scan_error: Checking the links who was in error during scan
    """
    errors_stat = False
    print(LINE)
    print("{} Error check".format(INFO))
    print(LINE)
    path_error = directory + "/errors.txt"
    if os.path.exists(path_error):
        with open(path_error) as read_links:
            for error_link in read_links.read().splitlines():
                try:
                    req = requests.get(error_link, verify=False)
                    if exclude:
                        cep = check_exclude_page(req, error_link, directory, forbi, HOUR=False)
                        if cep:
                            error_status = req.status_code
                            if error_status == 404 or error_status == 406:
                                pass
                            else:
                                print("{}[{}] {}".format(INFO, req.status_code, error_link))
                                errors_stat = True
                    else: 
                        error_status = req.status_code
                        if error_status == 404 or error_status == 406:
                            pass
                        else:
                            print("{}[{}] {}".format(INFO, req.status_code, error_link))
                            errors_stat = True
                except Exception:
                    pass
                sys.stdout.write("\033[34m[i] {}\033[0m\r".format(error_link))
                sys.stdout.flush()
            if errors_stat == False:
                print("{} Nothing error detected".format(PLUS))
        os.system("rm {}".format(path_error))
    else:
        print("{} Nothing error detected".format(PLUS))


def defined_thread(thread, i, score_next):
    """
    Defined_thread: to defined the threads number
    """
    #print("score: {}".format(score_next))
    thread_count = threading.active_count()
    res_time = 0
    try:
        start = time.time()
        req = requests.get(url, verify=False)
        end = time.time()
        res_time = end - start
    except Exception:
        pass
    if res_time != 0 and res_time < 1 and thread_count < 20:
        #automaticly 20 threads MAX
        score = 1
        if i == 40 and score_next == 0:
            return 1, i;
        elif i == 160 and score_next == 1:
            return 1, i;
        elif i == 340 and score_next == 2:
            return 1, i;
        else:
            return 0, score;
    else:
        return 0, 0;


def len_page_flush(len_p):
    """
    Len_page_flush: to defined the word size for then "flush" it
    """
    if len_p <= 10:
        return 15
    elif len_p > 10 and len_p <= 20:
        return 25
    elif len_p > 20 and len_p <= 30:
        return 35
    elif len_p > 30 and len_p <= 40:
        return 45
    elif len_p > 40 and len_p <= 50:
        return 55
    elif len_p > 50 and len_p <= 70:
        return 75
    else:
        return 100


def defined_connect(s, res, user_agent=False, cookie_auth=False):
    allow_redirection = True if stat == 301 or stat == 302 or redirect else False
    if cookie_auth:
        if redirect:
            req = s.get(res, headers=user_agent, allow_redirects=allow_redirection, verify=False, timeout=10)
            if "You need to enable JavaScript to run this app" in req.text or "JavaScript Required" in req.text or "without JavaScript enabled" in req.text:
                print("{}Need to enable JavaScript to run this app, this problem will be fix ASAP sorry".format(INFO))
                #sys.exit()
                #TODO
            else:
                return req
        else:
            req = s.get(res, headers=user_agent, allow_redirects=allow_redirection, verify=False, timeout=10, cookies=cookie_auth)
            if "You need to enable JavaScript to run this app" in req.text or "JavaScript Required" in req.text or "without JavaScript enabled" in req.text:
                print("{}Need to enable JavaScript to run this app, this problem will be fix ASAP sorry".format(INFO))
                #sys.exit()
                #TODO
            else:
                return req
    else:
        if redirect:
            req = s.get(res, headers=user_agent, allow_redirects=allow_redirection, verify=False, timeout=10)
            if "You need to enable JavaScript to run this app" in req.text or "JavaScript Required" in req.text or "without JavaScript enabled" in req.text:
                print("{}Need to enable JavaScript to run this app, this problem will be fix ASAP sorry".format(INFO))
                #sys.exit()
                #TODO
            else:
                return req
        else:
            req = s.get(res, headers=user_agent, allow_redirects=allow_redirection, verify=False)
            if "You need to enable JavaScript to run this app" in req.text or "JavaScript Required" in req.text or "without JavaScript enabled" in req.text:
                print("{}Need to enable JavaScript to run this app, this problem will be fix ASAP sorry".format(INFO))
                #sys.exit()
                #TODO
            else:
                return req


def thread_wrapper(i, q, threads, manager, t_event, directory=False, forced=False, u_agent=False):
    while not q.empty() and not t_event.isSet():
        #print("DEBUG: {}".format(t_event.isSet())) #DEBUG
        tryUrl(i, q, threads, manager, directory, forced, u_agent)


def test_timeout(url):
    """
    Test_timeout: just a little function for test if the connection is good or not
    """
    try:
        req_timeout = requests.get(url, timeout=50)
    except Timeout:
        print("{}Service potentialy Unavailable, The site web seem unavailable please wait...\n".format(WARNING))
        time.sleep(180)
    except requests.exceptions.ConnectionError:
        pass


def tryUrl(i, q, threads, manager=False, directory=False, forced=False, u_agent=False, nLine=False):
    """
    tryUrl:
    Test all URL contains in the dictionnary with multi-threading.
    This script run functions:
    - create_backup()
    - dl()
    - file_backup()
    - mail()
    """
    s = requests.session()
    parsing = parsing_html()
    thread_score = 0
    score_next = 0
    all_mail = []
    waf_score = 0
    percentage = lambda x, y: float(x) / float(y) * 100
    thread_i = 0
    stop_add_thread = False
    time_i = 120
    time_bool = False
    waf = False
    error_bool = False
    tested_bypass = False
    for numbers in range(len_w):
        thread_count = threading.active_count()
        thread_all = thread_count - 1
        now = time.localtime(time.time())
        hour_t = time.strftime("%H:%M:%S", now)
        HOUR = "\033[35m[{}] \033[0m".format(hour_t)
        res = q.get()
        page = res.split("/")[-1]
        if auto and not stop_add_thread:
            thrds, scores = defined_thread(threads, thread_score, score_next)
            if scores == 1:
                thread_score += 1
            if thrds == 1:
                threads += 1
                score_next += 1
                manager.add_thread(i, threads, manager)
            #print("{}: {}".format(threading.currentThread().getName() ,thread_score))#DEBUG
        try:
            if u_agent:
                user_agent = {'User-agent': u_agent}
            else:
                ua = UserAgent()
                user_agent = {'User-agent': ua.random} #for a random user-agent
            try:
                forbi = False
                if ts: #if --timesleep option defined
                    time.sleep(ts)
                req = defined_connect(s, res, user_agent, cookie_auth)
                if "robots.txt" in res.split("/")[3:] and req.status_code == 200:
                    print("{} {} {}".format(HOUR, PLUS, res))
                    for r in req.text.split("\n"):
                        print("\t- {}".format(r))
                waf = verify_waf(req, res, user_agent)
                #verfiy_waf function, to check if waf detected, True: detected # False: not detected
                if waf == True:
                    if tested_bypass == False:
                        print("{}We try to bypass it...".format(INFO))
                        try_bypass_waf = bypass_waf(req, res)
                        #print(try_bypass_waf) #DEBUG
                        #print(user_agent) #DEBUG
                        if try_bypass_waf == False: # if not worked not repeat
                            tested_bypass == True
                        elif try_bypass_waf and type(try_bypass_waf) is not bool:
                            user_agent.update(try_bypass_waf)
                    waf_score += 1
                    time_bool = True
                    if waf_score == 2:
                        waf_score = 0
                        if thread_count != 1:
                            thread_count += 1
                            stop_add_thread = True
                            print("{} Auto-reconfig scan to prevent the WAF".format(INFO))
                            manager.stop_thread()
                        #TODO: potentialy use TOR (apt install tor, pip install torrequest) for next requests after that.
                    #pass
                if backup:
                    hidden_dir(res, user_agent, directory, forbi, HOUR)
                if redirect and req.history:
                    for histo in req.history:
                        status_link = histo.status_code
                else:
                    status_link = req.status_code
                redirect_link = req.url
                redirect_stat = req.status_code
                #test backup files
                #print(status_link) #DEBUG status response
                if status_link == 200:
                    if exclude:
                        cep = check_exclude_page(req, res, directory, forbi, HOUR)
                        if cep:
                            print("{} {} {}".format(HOUR, PLUS, res))
                    else:
                        # dl files and calcul size
                        size = dl(res, req, directory)
                        if size:
                            print("{} {} {} ({} bytes)".format(HOUR, PLUS, res, size))
                            outpt(directory, res, stats=0)
                        else:
                            print("{} {} {}".format(HOUR, PLUS, res))
                            outpt(directory, res, stats=0)
                        #check backup
                        create_backup(res, directory, forbi)
                        #add directory for recursif scan
                        parsing.get_links(req, directory)
                        #scrape all link
                        if res[-1] == "/" and recur:
                            if ".git" in res:
                                pass
                            else:
                                spl = res.split("/")[3:]
                                result = "/".join(spl)
                                rec_list.append(result)
                    parsing.mail(req, directory, all_mail)
                    #report.create_report_url(status_link, res, directory)
                    #get mail
                    if 'sitemap.xml' in res:
                        parsing.sitemap(req, directory)
                    parsing.search_s3(res, req, directory)
                elif status_link == 403:
                    #pass
                    if res[-1] == "/" and recur:
                        if ".htaccess" in res or ".htpasswd" in res or ".git" in res or "wp" in res:
                            outpt(directory, res, stats=403)
                        else:
                            spl = res.split("/")[3:]
                            result = "/".join(spl)
                            rec_list.append(result)
                            outpt(directory, res, stats=403)
                        #report.create_report_url(status_link, res, directory)
                    if not forced:
                        forbi = True
                        print("{} {} {} \033[31m Forbidden \033[0m".format(HOUR, FORBI, res))
                        create_backup(res, directory, forbi)
                        outpt(directory, res, stats=403)
                        #report.create_report_url(status_link, res, directory)
                    elif not forced and recur:
                        pass
                    else:
                        #print("{}{} {} \033[31m Forbidden \033[0m".format(HOUR, FORBI, res))
                        pass
                elif status_link == 404:
                    pass
                elif status_link == 405:
                    print("{} {} {}").format(HOUR, INFO, res)
                    #report.create_report_url(status_link, res, directory)
                elif status_link == 301:
                    if redirect and redirect_stat == 200:
                        if exclude:
                            cep = check_exclude_page(req, res, directory, forbi, HOUR)
                            if cep:
                                print("{} {} {}\033[33m => {}\033[0m 301 Moved Permanently".format(HOUR, LESS, res, redirect_link))
                                parsing.search_s3(res, req, directory)
                                outpt(directory, res, stats=301)
                        else:
                            print("{} {} {}\033[33m => {}\033[0m 301 Moved Permanently".format(HOUR, LESS, res, redirect_link))
                            parsing.search_s3(res, req, directory)
                            outpt(directory, res, stats=301)
                            #report.create_report_url(status_link, res, directory)
                elif status_link == 304:
                    print("{}\033[33m[+] \033[0m {}\033[33m 304 Not modified \033[0m".format(HOUR, res))
                    parsing.search_s3(res, req, directory)
                    #report.create_report_url(status_link, res, directory)
                elif status_link == 302:
                    if redirect and redirect_stat == 200:
                        if exclude:
                            cep = check_exclude_page(req, res, directory, forbi, HOUR)
                            if cep:
                                print("{}{}{}\033[33m => {}\033[0m 302 Moved Temporarily".format(HOUR, LESS, res, redirect_link))
                                parsing.search_s3(res, req, directory)
                                outpt(directory, res, stats=302)
                        else:
                            print("{}{}{}\033[33m => {}\033[0m 302 Moved Temporarily".format(HOUR, LESS, res, redirect_link))
                            parsing.search_s3(res, req, directory)
                            outpt(directory, res, stats=302)
                            #report.create_report_url(status_link, res, directory)
                elif status_link == 400 or status_link == 500:
                    if "Server Error" in req.text or "Erreur du serveur dans l'application" in req.text:
                        if status_link == 400:
                            if exclude:
                                cep = check_exclude_page(req, res, directory, forbi, HOUR)
                                if cep:
                                    print("{} {} {} \033[31m400 Server Error\033[0m".format(HOUR, WARNING, res))
                                    outpt(directory, res, stats=400)
                            else:
                                print("{} {} {} \033[31m400 Server Error\033[0m".format(HOUR, WARNING, res))
                                outpt(directory, res, stats=400)
                            #report.create_report_url(status_link, res, directory)
                        elif status_link == 500:
                            if exclude:
                                cep = heck_exclude_page(req, res, directory, forbi, HOUR)
                                if cep:
                                    print("{} {} {} \033[31m500 Server Error\033[0m".format(HOUR, WARNING, res))
                                    outpt(directory, res, stats=500)
                            else:
                                print("{} {} {} \033[31m500 Server Error\033[0m".format(HOUR, WARNING, res))
                                outpt(directory, res, stats=500)
                            #report.create_report_url(status_link, res, directory)
                    else:
                        pass
                        #print("{}{} \033[33m400 Server Error\033[0m").format(LESS, res)
                elif status_link == 422 or status_link == 423 or status_link == 424 or status_link == 425:
                    print("{} {} {} \033[33mError WebDAV\033[0m".format(HOUR, LESS, res))
                    #report.create_report_url(status_link, res, directory)
                elif status_link == 401:
                    """print("{} {} {} \033[33m401 Unauthorized\033[0m".format(HOUR,LESS, res))
                    outpt(directory, res, stats=401)"""
                    pass
                elif status_link == 405:
                    print("{} {} {}".format(HOUR, PLUS, res))
                    outpt(directory, res, stats=405)
                elif status_link == 503:
                    req_test_index = requests.get(url, verify=False) # take origin page url (index) to check if it's really unavailable
                    if req_test_index.status_code == 503:
                        manager.stop_thread()
                        print("{}{} Service potentialy Unavailable, The site web seem unavailable please wait...\n".format(HOUR, WARNING))
                        time_bool = True
                    else:
                        pass
                elif status_link == 429 or status_link == 522:
                    req_test_many = requests.get(url, verify=False)
                    if req_test_many == 429 or status_link == 522:
                        print("{} {} Too many requests, web service seem to be offline".format(HOUR, WARNING))
                        print("STOP so many requests, we should wait a little...")
                        time_bool = True
                    else:
                        pass
                        #print("{}{}{} 429".format(HOUR, LESS, res))
                if backup:
                    fbackp = file_backup(s, res, directory, forbi, HOUR)
                    if fbackp == False:
                        with open(directory + "/errors.txt", "a+") as write_error:
                            write_error.write(res+"\n")
                        #errors = manager.error_check()
                        #error_bool = True
            except Timeout:
                #traceback.print_exc() #DEBUG
                with open(directory + "/errors.txt", "a+") as write_error:
                    write_error.write(res+"\n")
                #errors = manager.error_check()
                #error_bool = True
            except Exception:
                #traceback.print_exc() #DEBUG
                with open(directory + "/errors.txt", "a+") as write_error:
                    write_error.write(res+"\n")
                #errors = manager.error_check()#TODO
                #error_bool = True
            q.task_done()
        except Exception:
            pass
            #traceback.print_exc() #DEBUG
        len_p = len(page)
        len_flush = len_page_flush(len_p)
        if time_bool: #if a waf detected, stop for any seconds
            while time_i != 0:
                time_i -= 1
                time.sleep(1)
                print_time = "stop {}s |".format(time_i) if time_bool else ""
                #for flush display
                sys.stdout.write("\033[34m[i] {0:.2f}% - {1}/{2} | Threads: {3:} - {4} | {5:{6}}\033[0m\r".format(percentage(numbers+nLine, len_w)*thread_all, numbers*thread_all+nLine, len_w, thread_all, print_time, page, len_flush))
                sys.stdout.flush()
            time_i = 60
            time_bool = False
        else:
            sys.stdout.write("\033[34m[i] {0:.2f}% - {1}/{2} | Threads: {3:} | {4:{5}}\033[0m\r".format(percentage(numbers+nLine, len_w)*thread_all, numbers*thread_all+nLine, len_w, thread_all, page, len_flush))
            sys.stdout.flush()


def check_words(url, wordlist, directory, u_agent, thread, forced=False, nLine=False):
    """
    check_words:
    Functions wich manage multi-threading
    """
    #report = create_report_test()
    #report.create_report_base(directory, cookie_)
    if thread:
        threads = thread
    if auto:
        threads = 3
    link_url = []
    hiddend = []
    with open(wordlist, "r") as payload:
        links = payload.read().splitlines()
    state = links[nLine:] if nLine else links
    for link in state:
        link_url = url + prefix + link if prefix else url + link
        enclosure_queue.put(link_url)
    manager = ThreadManager(enclosure_queue)
    for i in range(threads):
        worker = Thread(target=tryUrl, args=(i, enclosure_queue, threads, manager, directory, forced, u_agent, nLine))
        worker.setDaemon(True)
        worker.start()
    enclosure_queue.join()
    """
        Recursif: For recursif scan
    """
    if rec_list != []:
        print(LINE)
        size_rec_list = len(rec_list)
        i_r = 0
        forced = True
        while i_r < size_rec_list:
            url_rec = url + rec_list[i_r]
            print("{}Entering in directory: {}".format(INFO, rec_list[i_r]))
            print(LINE)
            with open(wordlist, "r") as payload:
                links = payload.read().splitlines()
                for i in range(threads):
                    worker = Thread(target=tryUrl, args=(i, enclosure_queue, threads, directory, forced, u_agent))
                    worker.setDaemon(True)
                    worker.start()
                for link in links:
                    link_url = url + prefix + link if prefix else url + link
                    enclosure_queue.put(link_url)
                enclosure_queue.join()
                i_r = i_r + 1
            print(LINE)
    else:
        print("\n{}not other directory to scan".format(INFO))
    try:
        os.remove(directory + "/backup.txt")
    except:
        print("backup.txt not found")


def create_file(url, stat, u_agent, thread, subdomains):
    """
    create_file:
    Create directory with the website name to keep a scan backup.
    """
    ms = mini_scans()
    ds = detect_scans()
    dire = ''
    forbi = False
    if 'www' in url:
        direct = url.split('.')
        director = direct[1]
        dire = "{}.{}".format(direct[1], direct[2].replace("/",""))
        directory = "sites/" + director
    else:
        direct = url.split('/')
        director = direct[2]
        dire = director
        directory = "sites/" + director
    # if the directory don't exist, create it
    if not os.path.exists(directory):
        os.makedirs(directory) # creat the dir
        if subdomains:
            subdomain(subdomains)
        ms.get_header(url, directory)
        ms.get_dns(url, directory)
        ms.who_is(url, directory)
        result, v = ds.detect_cms(url, directory)
        if result:
            ds.cve_cms(result, v)
        dw = detect_waf(url, directory, thread)
        if dw:
            thread = dw
        ms.wayback_check(dire, directory)
        ms.gitpast(url)
        ms.firebaseio(url)
        status(stat, directory, u_agent, thread)
        scan_error(directory, forbi)
        create_report(directory, cookie_)
    # or else ask the question
    else:
        try:
            new_file = raw_input('This directory exist, do you want to create another directory ? [y/N]: ')
            print("\n")
        except:
            new_file = input('This directory exist, do you want to create another directory ? [y/N]: ')
            print("\n")
        if new_file == 'y':
            print(LINE)
            directory = directory + '_2'
            os.makedirs(directory)
            if subdomains:
                subdomain(subdomains)
            ms.get_header(url, directory)
            ms.get_dns(url, directory)
            ms.who_is(url, directory)
            result, v = ds.detect_cms(url, directory)
            if result:
                ds.cve_cms(result, v)
            dw = detect_waf(url, directory, thread)
            if dw:
                thread = dw
            ms.wayback_check(dire, directory)
            ms.gitpast(url)
            ms.firebaseio(dire)
            status(stat, directory, u_agent, thread)
            scan_error(directory, forbi)
            create_report(directory, cookie_)
        else:
            print(LINE)
            if subdomains:
                subdomain(subdomains)
            status(stat, directory, u_agent, thread)
            scan_error(directory, forbi)
            create_report(directory, cookie_)


if __name__ == '__main__':
    #arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", help="URL to scan [required]", dest='url')
    parser.add_argument("-w", help="Wordlist used for URL Fuzzing [required]", dest='wordlist')
    parser.add_argument("-s", help="Subdomain tester", dest='subdomains', required=False)
    parser.add_argument("-t", help="Number of threads to use for URL Fuzzing. Default: 20", dest='thread', type=int, default=20, required=False)
    parser.add_argument("-a", help="Choice user-agent", dest='user_agent', required=False)
    parser.add_argument("--redirect", help="For scan with redirect response (301/302)", dest='redirect', required=False, action='store_true')
    parser.add_argument("-r", help="Recursive dir/files", required=False, dest="recursif", action='store_true')
    parser.add_argument("-p", help="Add prefix in wordlist to scan", required=False, dest="prefix")
    parser.add_argument("-o", help="Output to site_scan.txt (default in website directory)", required=False, dest="output")
    parser.add_argument("-b", help="Add a backup file scan like 'exemple.com/~exemple/, exemple.com/ex.php.bak...' but longer", required=False, dest="backup", action='store_true')
    parser.add_argument("--cookie", help="Scan with an authentification cookie", required=False, dest="cookie_", type=str)
    parser.add_argument("--exclude", help="To define a page or response code status type to exclude during scan", required=False, dest="exclude")
    parser.add_argument("--timesleep", help="To define a timesleep/rate-limit if app is unstable during scan", required=False, dest="ts", type=float, default=0)
    parser.add_argument("--auto", help="Automatic threads depending response to website. Max: 20", required=False, dest="auto", action='store_true')
    parser.add_argument("--update", help="For automatic update", required=False, dest="update", action='store_true')
    results = parser.parse_args()
                                     
    url = results.url
    wordlist = results.wordlist
    subdomains = results.subdomains
    thread = results.thread
    u_agent = results.user_agent
    redirect = results.redirect
    recur = results.recursif
    prefix = results.prefix
    output = results.output
    backup = results.backup
    cookie_ = results.cookie_
    exclude = results.exclude 
    ts = results.ts
    auto = results.auto
    update = results.update

    banner()
    auto_update()
    len_w = 0 #calcul wordlist size
    cookie_auth = {}
    if url.split("/")[-1] != "":
        url = url + "/"
    if cookie_:
        s = cookie_.split(";")
        for c in s:
            if "=" in c:
                c = c.split("=", 1)
            elif ":" in c:
                c = c.split(":", 1)
            cookie_auth.update([(c[0],c[1])])
    with open(wordlist, 'r') as words:
        for l in words:
            len_w += 1
    if exclude:
        if len(exclude) < 4: #Defined if it's int for response http code or strings for url
            exclude = int(exclude)
        if type(exclude) == int:
            req_p = exclude
        else:
            req_exclude = requests.get(exclude, verify=False)
            req_p = req_exclude.text
    test_timeout(url)
    r = requests.get(url, allow_redirects=False, verify=False)
    stat = r.status_code
    print("\n \033[32m url " + url + " found \033[0m\n")
    print(LINE)
    create_file(url, stat, u_agent, thread, subdomains)
