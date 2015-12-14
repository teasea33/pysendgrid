# coding: utf-8

from retry import retry_on_exceptions
import requests
import datetime
import time
import json
import csv
import re


class SendGrid(object):
    def __init__(self, api_user, api_key, url_base="https://api.sendgrid.com"):
        self.api_user = api_user
        self.api_key = api_key
        self.url_base = url_base

        self.api_urls = {
            "newsletter": {  # create, clone, edit newsletter
                "add": "/api/newsletter/add.json",
                "edit": "/api/newsletter/edit.json",
                "list": "/api/newsletter/list.json",
                "get": "/api/newsletter/get.json",
                "del": "/api/newsletter/delete.json"},
            "lists": {  # recipient lists
                "add": "/api/newsletter/lists/add.json",
                "edit": "/api/newsletter/lists/edit.json",
                "get": "/api/newsletter/lists/get.json",
                "del": "/api/newsletter/lists/delete.json"},
            "email": {  # emails of recipient list
                "add": "/api/newsletter/lists/email/add.json",
                "edit": "/api/newsletter/lists/email/edit.json",
                "get": "/api/newsletter/lists/email/get.json",
                "del": "/api/newsletter/lists/email/delete.json"},
            "recipients": {  # recipients for a newsletter
                "add": "/api/newsletter/recipients/add.json",
                "get": "/api/newsletter/recipients/get.json",
                "del": "/api/newsletter/recipients/delete.json"},
            "schedule": {  # schedule to send
                "add": "/api/newsletter/schedule/add.json",
                "get": "/api/newsletter/schedule/get.json",
                "del": "/api/newsletter/schedule/delete.json"},
            "identity": {  # identities for newsletter
                "add": "/api/newsletter/identity/add.json",
                "list": "/api/newsletter/identity/list.json",
                "get": "/api/newsletter/identity/get.json"},
            "subuser": {  # create new subuser
                "add": "/apiv2/customer.add.json",
                "list": "/apiv2/customer.profile.json",
                "del": "/apiv2/customer.delete.json",
                "edit": "/apiv2/customer.profile.json"},
            "sendip": {  # create new subuser
                "add": "/apiv2/customer.sendip.json",
                "get": "/apiv2/customer.ip.json"},
            "apps": {
                "activate": "/apiv2/customer.apps.json",
                "customize": "/apiv2/customer.apps.json"},
            "category": {
                "create": "/api/newsletter/category/create.json",
                "del": "/api/newsletter/category/remove.json",
                "list": "/api/newsletter/category/list.json",
                "add": "/api/newsletter/category/add.json"},
            "stats": {
                "get": "/apiv2/customer.stats.json"},
            "unsubscribes": {
                "get": "/api/unsubscribes.get.json",
                "add": "/api/unsubscribes.add.json"}
        }

    def build_params(self, d=None):
        d = d or {}
        params = dict(api_user=self.api_user, api_key=self.api_key)
        params.update(d)
        return params

    def build_url(self, api, resource):
        try:
            return self.url_base + self.api_urls[api][resource]
        except KeyError:
            raise("url not found for %s api and %s resource" % (api, resource))

    @retry_on_exceptions(types=[Exception], tries=5, sleep=30)
    def call(self, api, resource, params=None):
        url = self.build_url(api, resource)
        call_params = self.build_params(params or {})
        response = requests.post(url, data=call_params)
        try:
            response_content = json.loads(response.content)
        except ValueError:
            response_content = {'error': re.search(r'<title>([^<]+)</title>', response.content).group(1)}

        with open("sendgrid.log", "a") as sendgridlog:
            sendgridlog.write(str(url) + " " + json.dumps(call_params) + " at " + datetime.datetime.now().isoformat() + "\n")
            sendgridlog.write(str(response_content) + " at " + datetime.datetime.now().isoformat() + "\n")

        return dict(success=True,
                    status_code=response.status_code,
                    url=response.url,
                    response=response_content)

    def get_newsletter(self, name):
        return self.call('newsletter', 'get', {"name": name})

    def list_newsletter(self, name=None):
        return self.call('newsletter', 'list', {"name": name} if name else {})

    def add_newsletter(self, name, subject, html, text=None, identity=None):
        if not identity:
            try:
                identity = self.list_identity()['response'][0]['identity']
            except Exception:
                raise("You have to inform the identity name")
        text = text or html  # TODO: clean HTML tags
        d = dict(identity=identity,
                 name=name,
                 subject=subject,
                 text=text,
                 html=html)
        return self.call('newsletter', 'add', d)

    def del_newsletter(self, name):
        return self.call('newsletter', 'del', dict(name=name))

    def clone_newsletter(self, existing_name, new_name):
        existing = self.get_newsletter(existing_name)['response']
        if isinstance(existing, dict):
            new = self.add_newsletter(
                name=new_name,
                subject=existing['subject'],
                html=existing['html'],
                text=existing['text'],
                identity=existing['identity']
                )
            return new
        return existing

    def edit_newsletter(self, **fields):
        '''fields must be name, newname, subject, text, html'''
        identity = fields.pop('identity', None)
        if identity is None:
            identity = self.list_identity()['response'][0]['identity']
        return self.call('newsletter', 'edit', dict(**fields))

    def list_identity(self, name=None):
        return self.call('identity', 'list', {"name": name} if name else {})

    def add_identity(self, **fields):
        '''Fields required are: city, state, zip, address, country, name, email, identity'''
        return self.call('identity', 'add', dict(**fields))

    def get_identity(self, identity):
        return self.call('identity', 'get', {"identity": identity})

    def add_list(self, name):
        return self.call('lists', 'add', {"list": name})

    def get_list(self, name=None):
        return self.call('lists', 'get', {"list": name} if name else {})

    def del_list(self, name):
        return self.call('lists', 'del', dict(list=name))

    def edit_list(self, list, newlist):
        return self.call('lists', 'edit', dict(list=list, newlist=newlist))

    def add_email_to(self, **fields):
        return self.call('email', 'add', dict(**fields))

    def del_email_from(self, **fields):
        '''fields can be list, and email'''
        return self.call('email', 'del', dict(**fields))

    def add_emails_to(self, list_name, emails):
        """adds a list of emails
        [{'email': 'jon@jon.com', 'name': 'Jon'}, {'email': 'mary@mary.com', 'name': 'Mary'}]
        """
        #email_data = []
        for i, email in enumerate(emails):
            emails[i] = json.dumps(email)
        #data = json.dumps(email_data)
        return self.call('email', 'add', dict(list=list_name, data=emails))

    def get_email(self, list_name, **fields):
        return self.call('email', 'get', dict(list=list_name, **fields))

    def add_recipients(self, newsletter_name, list_name):
        times = 10
        while times:
            print "trying to add recipient: %s" % times
            api_call = self.call('recipients', 'add', {"name": newsletter_name, "list": list_name})
            if 'error' in api_call['response']:
                if 'without recipients' in api_call['response']['error']:
                    time.sleep(30)
                times -= 1
            else:
                times = 0
        return api_call

    def get_recipients(self, newsletter_name):
        return self.call("recipients", "get", dict(name=newsletter_name))

    def del_recipients(self, newsletter_name, list):
        return self.call("recipients", "del", dict(name=newsletter_name, list=list))

    def add_schedule(self, newsletter_name, at=None, after=None):
        if at:
            print "time ", at.isoformat()
            d = dict(name=newsletter_name, at=at.isoformat())
        elif after:
            d = dict(name=newsletter_name, after=after)
        else:
            d = dict(name=newsletter_name)
        return self.call('schedule', 'add', d)

    def get_schedule(self, name):
        return self.call('schedule', 'get', dict(name=name))

    def del_schedule(self, name):
        return self.call('schedule', 'del', dict(name=name))

    def add_subuser(self, **fields):
        return self.call('subuser', 'add', dict(**fields))

    def list_subusers(self):
        return self.call('subuser', 'list', dict(task="get"))

    def del_subuser(self, user):
        return self.call('subuser', 'del', dict(user=user))

    def edit_subuser(self, user, **fields):
        '''fields can be first_name, last_name, address, city, state, country, zip, phone,
        website, company'''
        return self.call('subuser', 'edit', dict(task="set", user=user, **fields))

    def add_sendip(self, **fields):
        '''Fields can be task, user, set, ip'''
        return self.call('sendip', 'add', dict(task="append", **fields))

    def activate_app(self, user, name):
        return self.call('apps', 'activate', dict(task="activate", user=user, name=name))

    def customize_app(self, user, name, settings):
        return self.call('apps', 'customize',
            dict(task="setup", user=user, name=name, **settings))

    def add_category(self, category, name):
        return self.call('category', 'add', dict(category=category, name=name))

    def create_category(self, category):
        return self.call('category', 'create', dict(category=category))

    def del_category(self, category, name):
        return self.call('category', 'del', dict(category=category, name=name))

    def get_category_stats(self, category, user):
        '''other fields can be days, start_date, end_date'''
        return self.call('stats', 'get', dict(category=category, user=user))

    def get_unsubscribes(self):
        return self.call('unsubscribes', 'get')

    def add_unsubscribe(self, email):
        return self.call('unsubscribes', 'add', dict(email=email))

    def warm_up_from_csv(self,
                        csv_path,  # name, email csv string (no header)
                        newsletter_name,  # existing newsletter_name to be cloned
                        list_prefix,  # prefix to be used to name newsletter and lists created
                        interval=0,  # the first sending will be for how many recipients?
                        interval_step=0,  # increase interval at step
                        start_count=0,
                        start_send_at=None,  # when to start the sending - datetime object?,
                        start_send_after=None,  # count to start send
                        send_interval=1,  # interval in days
                        keys=("name", "email"),
                        chunk_size=50
                        ):
        """
        Example:
        sg = SendGrid(...., ....)
        # calculate dates by your own
        # damm SendGrid does not support timezone
        send_at = datetime.datetime(2012, 7, 30) + datetime.timedelta(hours=14)
        l = sg.warm_up_from_csv("myelails.csv",
                           "mynewsletter",
                           "my_sending",
                           interval=500,
                           interval_step=200,
                           start_send_at=send_at,
                           keys=("name", "email", "referer"),
                           chunk_size=50
                        )
        """
        # chuck size > 50 leads in to URL too large error
        assert chunk_size <= 50, "Maximum size for chunk is 50"
        # date
        assert any([start_send_at, start_send_after]), "Needs to define even start date or after in minutes"
        # split csv recipients in groups, by defined interval and increasing
        lists = {}
        lists_send_date = {}
        f = open(csv_path, 'r')
        reader = csv.reader(f)
        out = [dict(zip(keys, prop)) for prop in reader]
        # TODO
        # remove invalid email addresses
        # remove duplicates
        total = len(out)
        send_interval = datetime.timedelta(days=send_interval)
        if start_send_at:
            day_start = start_send_at
        elif start_send_after:
            day_start = datetime.datetime.now() + datetime.timedelta(minutes=start_send_after)
        else:
            day_start = datetime.datetime.now() + send_interval
        assert isinstance(day_start, datetime.datetime), "start_send_at must be datetime"
        if not interval:
            interval = 500
        if not interval_step:
            interval_step = 200
        for i in xrange(total):
            if start_count < interval:
                l = lists.setdefault(str(day_start.isoformat()), [])
                lists_send_date.setdefault(str(day_start.isoformat()), day_start)
                l.append(out[i])
                start_count += 1
            else:
                # day_start += send_interval
                # interval += interval_step
                # start_count = 0
                l = lists.setdefault(str(day_start.isoformat()), [])
                lists_send_date.setdefault(str(day_start.isoformat()), day_start)
                l.append(out[i])
                day_start += send_interval
                interval += interval_step
                start_count = 0

        list_names = lists.keys()

        # create a list for each group of recipients
        for list_name in list_names:
            print "Creating list %s" % list_name
            print self.add_list(list_prefix + "_" + list_name), list_name

        # clone the newsletter for each group of recipients
        for list_name in list_names:
            print "Cloning newsletter %s in to %s" % (newsletter_name, list_prefix + "_" + list_name)
            print self.clone_newsletter(newsletter_name, list_prefix + "_" + list_name)

        # # add recipients to each created list
        # already_included = []
        # # reads the status file
        # try:
        #     with open(list_prefix + "_status.txt", 'r') as status:
        #         for line in status:
        #             d = json.loads(line)
        #             already_included.append(d['email'])
        # except:
        #     pass  # first time, no need to read

        # call the api for each recipient
        # for list_name, recipients in lists.items():
        #     for i, recipient in enumerate(recipients):
        #         if not recipient['email'] in already_included:
        #             try:
        #                 print list_name, i, recipient['email'], self.add_email_to(list_prefix + "_" + list_name, **recipient)
        #                 with open(list_prefix + "_status.txt", 'a') as status:
        #                     msg = json.dumps(recipient) + "\n"
        #                     status.write(msg)
        #             except Exception, e:
        #                 with open(list_prefix + "_error.txt", 'a') as error:
        #                     print str(e)
        #                     error.write(str(e) + str(datetime.datetime.now()))

        # call the api for chunks of 50 recipients (url limit)
        for list_name, recipients in lists.items():
            # ensure each recipient is unique
            # because dict is not hashable
            for i, item in enumerate(recipients):
                item['index'] = i
            # split recipient list in chunks of 500 items
            starts = [recipients.index(item) for item in recipients[0::chunk_size]]
            for start in starts:
                try:
                    end = starts[starts.index(start) + 1]
                except IndexError:
                    end = len(recipients)
                recipient_chunk = recipients[start:end]
                print self.add_emails_to(list_prefix + "_" + list_name, recipient_chunk)

        # add each list to respective newsletter
        for list_name in list_names:
            print "adding list %s to newsletter %s" % (list_name, list_prefix + "_" + list_name)
            print self.add_recipients(list_prefix + "_" + list_name, list_prefix + "_" + list_name)

        # scheduling the sending for the respective date
        for list_name in list_names:
            print "Schedulling sending for %s" % list_prefix + "_" + list_name
            date_to_send = lists_send_date[list_name]
            print self.add_schedule(list_prefix + "_" + list_name, at=date_to_send)

        return (True, list_names, lists_send_date)
