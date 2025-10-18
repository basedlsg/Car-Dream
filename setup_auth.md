# Setup Authentication

Follow these steps to authenticate with Google Cloud SDK and set the Gemini API key:

1.  **Install Google Cloud SDK (if not already installed):**

    ```bash
    curl -sSL https://sdk.cloud.google.com | bash
    exec -l $SHELL
    ```

2.  **Authenticate with Google Cloud SDK:**

    ```bash
    gcloud auth login
    ```

3.  **Set the project ID:**

    ```bash
    gcloud config set project [YOUR_PROJECT_ID]
    ```

    **Note:** Replace `[YOUR_PROJECT_ID]` with your Google Cloud project ID. You can find your project ID in the Google Cloud Console.

4.  **Set the Gemini API key as an environment variable:**

    ```bash
    export GEMINI_API_KEY="AIzaSyAqko3NqGS-GtXhzm8LeiZ3xUEyo_XIqLo"
    ```

    **Note:** It is recommended to set the environment variable in your `.bashrc` or `.zshrc` file for persistence.