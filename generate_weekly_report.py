import urllib
import datetime
import sys
import argparse

import yaml
import requests


class PivotalClient(object):

    tracker_token = None
    api_uri = None
    projects = None

    PROJECT_ENTITIES = ('stories',)

    def __init__(self, **kwargs):

        self.tracker_token = kwargs.get('tracker_token')
        if not self.tracker_token:
            raise ValueError('tracker_token not set')

        self.api_uri = kwargs.get('api_uri')
        if not self.api_uri:
            raise ValueError('api_uri not set')
        if self.api_uri[-1] != '/':
            self.api_uri += '/'
        self.projects = kwargs.get('project_id')
        self.get_projects(self.projects)
        
    def _serialize_uri_params(self, **params):
        return '&'.join(
            [
                "{}={}".format(
                    k,
                    urllib.parse.quote_plus(v)
                ) for k, v in params.items()
            ]
        )

    def _prepare_headers(self):
        return {
            'X-TrackerToken': self.tracker_token
        }

    def get_projects(self, project_id):
        self.projects = []
        if not project_id:
            r = requests.get(self.api_uri+'/projects', headers=self._prepare_headers())
            for i in r.json():
                self.projects.append(i['id'])
        else:
            
            self.projects = [project_id]

    def _create_path(self, project, entity):
        if entity in self.PROJECT_ENTITIES:
            return 'projects/{}/{}'.format(project, entity)
        else:
            return entity

    def get(self, entity, **params):
        if entity[0] == '/':
            entity = entity[1:]
        answer = []
        for project in self.projects:
            path = self._create_path(project, entity)
            uri = '{}{}?{}'.format(
                self.api_uri,
                path,
                self._serialize_uri_params(**params)
            )
            headers = self._prepare_headers()
            r = requests.get(uri, headers=headers)
            r.raise_for_status()
            for story in r.json():
                answer.append(story)
        return answer
    
    def me(self):
        uri = '{}{}'.format(
                self.api_uri,
                self._create_path(self.projects[0], 'me'),
        )
        r = requests.get(uri, headers=self._prepare_headers())
        r.raise_for_status()
        return r.json()
    
class PivotalReportGenerator(object):

    def __init__(self, pivotal_client):
        self.client = pivotal_client

    def weekly_report(self, weeks_ago=0):
        report = '\n'
        
        me = self.client.me()
        
        today = datetime.datetime.now() - datetime.timedelta(weeks=weeks_ago)
        
        monday = today - datetime.timedelta(days=today.weekday())
        monday = monday.replace(hour=8, minute=0, second=0)

        friday = today + datetime.timedelta(days=(4-today.weekday()))
        friday = friday.replace(hour=20, minute=0, second=0)

        all_stories = self.client.get(
            'stories',
            updated_after=monday.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            updated_before=friday.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            fields="url,name,owner_ids"
        )
        report += 'Tasks owned by {}, updated after {} and before {}\n\n'.format(
            me['name'],
            monday.strftime("%Y-%m-%d %H:%M"),
            friday.strftime("%Y-%m-%d %H:%M"),
        )

        owned_stories = filter(lambda s: me['id'] in s['owner_ids'], all_stories)
        for s in owned_stories:
            report += s['url'] + '\n'
            report += s['name'] + '\n'
            report += '\n'

        return report[:-1]


if __name__ == '__main__':
    
    with open('config.yaml', 'r') as stream:
        try:
            config = yaml.load(stream)
        except yaml.YAMLError as exc:
            print(exc)
            sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weeks-ago",
        type=int,
        help="0 for current week (default), 1 for previous and so on",
        default=0,
    )
    args = parser.parse_args()

    pivotal_client = PivotalClient(
        tracker_token=config['pivotal']['tracker_token'],
        api_uri=config['pivotal']['api_uri'],
        project_id=config['pivotal']['project_id'],
    )

    generator = PivotalReportGenerator(
        pivotal_client=pivotal_client
    )

    print(generator.weekly_report(weeks_ago=args.weeks_ago))
