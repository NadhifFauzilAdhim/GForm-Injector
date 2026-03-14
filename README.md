
# Google Form Injector

A web application built with **Streamlit** that allows users to **automatically send data to Google Forms** using HTTP POST requests (`formResponse` endpoint).

This tool is designed to perform **bulk submission to Google Forms using CSV datasets** with a **flexible mapping system between dataset columns and Google Form entries (`entry.XXXX`)**.

This application is useful for:

- Survey automation
- Google Form testing
- Respondent simulation
- Bulk data submission

---

# Features

## CSV Dataset Upload

Users can upload a CSV dataset that will be used as the data source.

After uploading:

- the dataset preview will be displayed
- all CSV columns will be automatically detected

---

# Flexible Entry Mapping

Users can map **CSV columns** to **Google Form entries**.

Example mapping:

| Google Form Entry | Dataset Column |
|-------------------|---------------|
| entry.976363616 | name |
| entry.1808387689 | business_name |
| entry.1094522194 | address |

This mapping can be configured directly through the application UI.

---

# Automatic Mapping from Raw Payload

The application also supports **automatic mapping using raw Google Form payload**.

Users can copy the payload request from the **Network Tab in the browser** when submitting a Google Form.

Example raw payload:

```
entry.336054809=Hello
&entry.2012804322=123
&entry.1418407048=Baik
&entry.913138645=X
&dlut=1773487833514
&entry.913138645_sentinel=
&fvv=1
&partialResponse=%5Bnull%2Cnull%2C%22-8822633991432356214%22%5D
&pageHistory=0
&fbzx=-8822633991432356214
&submissionTimestamp=1773487837965
```

The application will automatically:

1. Parse the payload
2. Extract all `entry.XXXX` fields
3. Generate an initial mapping template
4. Build a payload configuration automatically

Example parsed fields:

```
entry.336054809
entry.2012804322
entry.1418407048
entry.913138645
```

Metadata fields such as the following will also be recognized:

```
fvv
pageHistory
partialResponse
fbzx
submissionTimestamp
```

This feature allows users to **avoid manually searching for entry IDs**.

---

# Static Value Support

Users can also provide static values instead of using CSV data.

Example:

```
entry.1682282680 = "Female"
entry.441895074 = "Rp 25 Million - Rp 250 Million"
```

---

# Random Data Generator

The application provides built-in random generators for survey simulation.

Available generators:

- Likert Scale (4 / 5)
- Age Range
- Education Level
- Business Duration

Example function:

```
def get_random_likert():
    return random.choice(["4","5"])
```

---

# Delay Control (Anti-Spam)

To prevent detection as spam by Google Forms, the application provides request delay configuration.

Example:

```
Min Delay: 1.5s
Max Delay: 3.5s
```

The delay is implemented using:

```
time.sleep(random.uniform(min_delay,max_delay))
```

---

# Payload Preview

Before executing the injection, the application will display a preview of the payload to be sent.

Example:

```
payload = {
    "entry.976363616": "Siti Aminah",
    "entry.1808387689": "Warung Berkah",
    "entry.1094522194": "Sukasari District",
    "entry.1682282680": "Female",
    "entry.441895074": "Rp 25 Million - Rp 250 Million",
    "entry.451572495": "Culinary",
    "entry.1151358127": "5",
    "entry.2018635405": "4",
    "fvv": "1",
    "pageHistory": "0,1,2,3"
}
```

---

# How Google Form Injection Works

Google Forms accepts responses through the endpoint:

```
https://docs.google.com/forms/d/e/FORM_ID/formResponse
```

Data is sent using:

```
POST
Content-Type: application/x-www-form-urlencoded
```

Each field in the form has a parameter named:

```
entry.<ID>
```

Example:

```
entry.123456789
entry.987654321
```

---

# Google Form Metadata

Some additional fields are usually included in the payload.

### fvv

Used internally by Google Forms for validation.

```
fvv = 1
```

---

### pageHistory

Represents the pages visited in multi-page forms.

Example:

```
pageHistory = "0,1,2,3"
```

---

### Sentinel Fields

Usually appear in matrix or Likert questions.

Example:

```
entry.913138645_sentinel = ""
```

---

# Project Structure

```
project/
│
├── app.py
├── utils/
    ├── csv_handler.py
    ├── form_handler.py
    └── generators.py
```

---

# Installation

Clone the repository:

```
https://github.com/NadhifFauzilAdhim/GForm-Injector.git
```

Navigate to the project folder:

```
cd gform-injector
```

Install dependencies:

```
pip install -r requirements.txt
```

---

# Run the Application

Start the Streamlit application:

```
streamlit run app.py
```

Open in your browser:

```
http://localhost:8501
```

---

# Example Workflow

1 Upload CSV dataset  
2 Enter Google Form `/formResponse` URL  
3 Paste raw payload or configure manual mapping  
4 Configure request delay  
5 Preview payload  
6 Click **Start Injection**  
7 Monitor progress and logs  

---

# Warning

Use this tool **responsibly**.

Do not use it for:

- spamming Google Forms
- manipulating research data
- violating platform policies

This tool is intended only for **automation testing and research purposes**.

---

# License

MIT License
