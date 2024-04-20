#!/bin/bash

if ! command -v jq &> /dev/null
then
    echo "jq has to be installed for running this script"
    exit 1
fi

#UNIFIED_URL="http://localhost:8046"
#USERNAME="admin"
#PASSWORD="password"
#REPO="example-repo-local"
#REPO="maven-remote"
LAST_DAYS=90

# Usage Example:
# ./repo-xray-indexable-artifacts.sh -r example-repo-local -j http://localhost:8046 -u admin -p password

usage() {                                
  echo "Usage: $0 -r REPO_NAME -j JFROG_PLATFORM_URL -u USERNAME -p PASSWORD [-d LAST_DAYS]" 1>&2 
}
exit_abnormal() { 
  usage
  exit 1
}

while getopts ":r:j:u:p:d:" opt; do
  case "${opt}" in          
    r)                                    
      REPO=${OPTARG} 
      ;;
    j)                                    
      UNIFIED_URL=${OPTARG} 
      ;;
    u)                                    
      USERNAME=${OPTARG} 
      ;;
    p)                                    
      PASSWORD=${OPTARG} 
      ;;
    d)                                   
      LAST_DAYS=${OPTARG}                    
      re_isanum='^[0-9]+$'                
      if ! [[ $LAST_DAYS =~ $re_isanum ]] ; then  
        echo "Error: LAST_DAYS must be a positive integer"
        exit_abnormal
      elif [ $LAST_DAYS -eq "0" ]; then      
        echo "Error: LAST_DAYS must be greater than zero"
        exit_abnormal                   
      fi
      ;;
    :)                                    # If expected argument omitted:
      echo "Error: -${OPTARG} requires an argument"
      exit_abnormal                       
      ;;
    \?)                                    # If unknown (any other) option:
      echo "Invalid option: -$OPTARG" >&2
      exit_abnormal                       
      ;;
  esac
done

if [ -z "$REPO" ]; then
    echo "Mandatory 'Repository' argument (-r REPO_NAME) has to be provided"
    exit_abnormal
elif [ -z "$UNIFIED_URL" ]; then
    echo "Mandatory 'JFrog Platform Url' argument (-j JFROG_PLATFORM_URL) has to be provided"
    exit_abnormal
elif [ -z "$USERNAME" ]; then
    echo "Mandatory 'JFrog Platform Username' argument (-u USERNAME) has to be provided"
    exit_abnormal
elif [ -z "$PASSWORD" ]; then
    echo "Mandatory 'JFrog Platform Password' argument (-p PASSWORD) has to be provided"
    exit_abnormal
fi

repoType=$(curl -s -u$USERNAME:$PASSWORD $UNIFIED_URL/artifactory/api/repositories/$REPO | jq -r .packageType)
if [ -z "$repoType" ] || [ "$repoType" == "null" ] 
then
    echo "Failed to get repository package type for $REPO"
    exit 1
fi

rClass=$(curl -s -u$USERNAME:$PASSWORD $UNIFIED_URL/artifactory/api/repositories/$REPO | jq -r .rclass)
if [ -z "$rClass" ] || [ "$rClass" == "null" ] 
then
    echo "Failed to get repository type for $REPO"
    exit 1
elif [ "$rClass" != "local" ] && [ "$rClass" != "remote" ]
then
    echo "Only local and remote repositories are supported (repoType: $rClass)"
    exit 1
elif [ "$rClass" == "remote" ]
then
    REPO+="-cache"
fi

aqlFilter=$(curl -s -u$USERNAME:$PASSWORD $UNIFIED_URL/xray/api/v1/supportedTechnologies | jq --arg repoType "$repoType" '.supported_package_types | map(select(.type == $repoType).extensions[]) | map(if .is_file != true then {"name" : {"$match":("*"+.extension)}} else {"name" : {"$eq":.extension}} end)')
if [ $? -ne 0 ]; then
   echo "Failed to query Xray for filter of indexable Artifacts in $REPO"
   exit 1
fi

read -r -d '' timeFilter <<- EOM
  "\$or":[
    {"created" : {"\$last" : "${LAST_DAYS}d"}},
    {"modified" : {"\$last" : "${LAST_DAYS}d"}}
  ]
EOM
aqlQuery="items.find({\"repo\":\"$REPO\",\"\$or\":$aqlFilter,$timeFilter}).include(\"path\",\"name\",\"created\",\"modified\")"

resultsFileName="xray-indexable-artifacts.json"
rm -f $resultsFileName
curl -u$USERNAME:$PASSWORD -X POST -H 'Content-Type:text/plain' $UNIFIED_URL/artifactory/api/search/aql --data "$aqlQuery" > $resultsFileName
if [ $? -ne 0 ]; then
   echo "Failed to query Artifactory for paths of indexable artifacts in $REPO"
   exit 1
fi

