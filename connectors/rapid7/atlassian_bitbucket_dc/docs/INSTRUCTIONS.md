# __Description__
  Connector for Atlassian Bitbucket Data Center

# __Overview__

  The Bitbucket Data Center connector allows Surface Command users to explore the relationships
  between their Bitbucket Data Center Projects and Repositories.

  This connector synchronizes Bitbucket projects and repositories with the Surface Command platform.

# __Documentation__

  To authentic with the Bitbucket Data Center API, you are required to set the following:

  * `Base URL`: the local URL including the Port used to access the local instance of Atlassian Bitbucket Data Center
  * `Username`: the username used to login to the instance
  * `Personal Access Token`: the Access Token for the user. See the Bitbucket [documentation](https://confluence.atlassian.com/bitbucketserver/http-access-tokens-939515499.html) on how to create one
  * `Skip Archived Repositories?`: if enabled, skip archived repositories during the import