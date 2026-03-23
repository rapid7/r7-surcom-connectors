# __Description__

  Connector for Kaseya VSA 9

# __Overview__

  Kaseya VSA is cloud based Remote Monitoring and Management (RMM) Software built for IT Professionals. You can monitor, manage, and secure any endpoint, from anywhere.

  This connector synchronizes details of all assets and agents known to Kaseya VSA 9 into Rapid7 Surface Command.

# __Documentation__

  To configure the Kaseya VSA 9 connector, you need the following settings:
  
  ### Required Settings

  - **URL**: Base URL of your Kaseya VSA 9 instance
    This is the base endpoint URL used to authenticate and access all Kaseya VSA 9 API endpoints. Obtain this URL from the web address bar when you connect to VSA 9. For example: https://vsa01.kaseya.net/

  - **Username**: Your Kaseya VSA 9 username or email address used to log in to the VSA 9 instance.

  - **Personal Access Token**: A Personal Access Token generated in Kaseya VSA 9. 
    This token is used together with your username for API authentication. 
    Refer to the [Kaseya VSA 9 documentation](https://helpdesk.kaseya.com/hc/en-gb/articles/4705556673169-Use-VSA-Access-Token-API) 
    to generate a Personal Access Token in your VSA 9 instance.

