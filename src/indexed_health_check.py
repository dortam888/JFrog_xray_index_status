import requests
import pandas as pd
import subprocess
import os
import math

threshold = 80


def highlight_below_threshold(val):
    if val['index_percantage'] < threshold:
        color = 'background-color: #ffe6e6'
    elif math.isnan(val['index_percantage']):
        color = 'background-color: white'
    else:
        color = 'background-color: #e6ffe6'
    return [color] * len(val)


def get_repository_index_status(art_url, access_token):
    get_repos_request = art_url + "/xray/api/v1/binMgr/default/repos"
    headers = {"Authorization": "Bearer" + " " + access_token}

    repos = requests.get(url=get_repos_request, headers=headers)

    if repos.status_code != 200:
        print("Error:", repos.text)
        exit()

    return repos.json()


def create_table_of_repositories(repositories):
    indexed_repos = repositories.get('indexed_repos', [])
    indexed_repos_table = pd.DataFrame(indexed_repos)
    non_indexed_repos = repositories.get('non_indexed_repos', [])
    non_indexed_repos_table = pd.DataFrame(non_indexed_repos)

    return indexed_repos_table, non_indexed_repos_table


def count_artifacts(art_url, access_token, index_repos):

    max_num_of_days_retention = 1000
    indexable_script_location = "../indexable_script/repo-xray-indexable-artifacts.sh"
    list_of_artifacts = []

    for repository_name in index_repos['name']:
        script = "%s -r %s -j %s -p %s -d %d" % (indexable_script_location, repository_name, art_url, access_token, max_num_of_days_retention)
        subprocess.run([script], shell=True)
        count_in_file_command = "cat xray-indexable-artifacts.json | jq '.range.total'"
        number_of_artifacts = subprocess.run(count_in_file_command, shell=True, capture_output=True, text=True)
        list_of_artifacts.append(int(number_of_artifacts.stdout))

    index_repos['indexable_artifacts'] = list_of_artifacts
    return index_repos


def count_indexed_artifacts(art_url, access_token, index_repos):
    list_of_indexed_artifacts = []

    for repository_name in index_repos['name']:
        if repo_type(art_url, access_token, repository_name) == 'remote':
            repository_name = repository_name + "-cache"
        headers = {"Authorization": "Bearer" + " " + access_token}
        offset = 0
        num_of_indexed_artifacts = 0

        while True:
            offset_string = "/xray/api/v1/artifacts?num_of_rows=1000&repo=%s&offset=%d" % (repository_name, offset)
            get_artifacts_api = art_url + offset_string
            response = requests.get(get_artifacts_api, headers=headers)
            if response.status_code != 200:
                print("Error:" + response.text)
            json_object = response.json()
            if json_object['data'] is None:
                num_of_indexed_artifacts = 0
            else:
                num_of_indexed_artifacts = num_of_indexed_artifacts + len(json_object['data'])
            if json_object['offset'] == -1:
                break
            offset = json_object['offset']

        list_of_indexed_artifacts.append(num_of_indexed_artifacts)

    index_repos['indexed'] = list_of_indexed_artifacts
    return index_repos


def repo_type(art_url, access_token, repository_name):
    repo_type_request = art_url + "/artifactory/api/repositories/" + repository_name
    headers = {"Authorization": "Bearer" + " " + access_token}
    response = requests.get(repo_type_request, headers=headers)
    return response.json()['rclass']


def style_tables(indexed_repos_table, non_indexed_repos_table):
    indexed_repos_table = indexed_repos_table.sort_values(by='index_percantage', ascending=False)
    styled_df = indexed_repos_table.style.apply(highlight_below_threshold, axis=1)
    styled_df.to_html("indexed_health_check.html")
    indexed_repos_table.to_csv("indexed_artifacts.csv", index=False)
    non_indexed_repos_table.to_csv("non_indexed_artifacts.csv", index=False)


def indexed_health_check(art_url, access_token):
    repos = get_repository_index_status(art_url, access_token)
    indexed_repos_table, non_indexed_repos_table = create_table_of_repositories(repos)
    indexed_repos_table = count_indexed_artifacts(art_url, access_token, indexed_repos_table)
    indexed_repos_table = count_artifacts(art_url, access_token, indexed_repos_table)
    indexed_repos_table['index_percantage'] = indexed_repos_table['indexed'] / indexed_repos_table['indexable_artifacts'] * 100

    style_tables(indexed_repos_table, non_indexed_repos_table)


if __name__ == "__main__":
    url = os.getenv('ART_URL')
    token = os.getenv('ART_ACCESS_TOKEN')
    indexed_health_check(url, token)
