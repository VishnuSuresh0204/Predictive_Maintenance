# Predictive Maintenance

A Django-based predictive maintenance system for monitoring industrial machines, recording sensor data, forecasting failure risk using a machine learning model, and managing maintenance workflows.

## Overview

This project helps organizations:

- register and manage machines
- collect sensor readings such as temperature, torque, speed, and tool wear
- run predictive failure analysis using an ML model
- view risk alerts and prediction history
- log maintenance activities and track downtime/costs
- manage multiple organizations from an admin dashboard

## Tech Stack

- Python 3.11
- Django 5.2
- SQLite database
- Scikit-learn / NumPy / Pandas / SciPy
- HTML, CSS, JavaScript templates

## Project Structure

```text
Predictive_Maintenance/
├── env/                       # Virtual environment
├── maintain/                  # Django project root
│   ├── manage.py
│   ├── db.sqlite3
│   ├── maintain/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── ...
│   └── myapp/
│       ├── models.py
│       ├── views.py
│       ├── ml/
│       ├── migrations/
│       └── templates/
├── .gitignore
├── README.md
└── ...
```

## Features

### Organization Features
- Register an organization account
- Manage organization profile
- Add, edit, and delete machines
- Enter live sensor readings
- View machine details and prediction history
- Review alerts and acknowledge/resolve them
- Schedule and update maintenance records

### Admin Features
- Manage organizations and machine data
- Review all predictions and alerts
- Configure organization risk thresholds
- View maintenance and reporting dashboards

## Setup Instructions

1. Open a terminal in the project root.
2. Activate the virtual environment:

```bash
cd e:\project26\Predictive_Maintenance
env\Scripts\activate
```

3. Install dependencies if needed:

```bash
pip install -r requirements.txt
```

If a requirements file is not present, install the project dependencies manually in the activated environment:

```bash
pip install django pandas numpy scipy scikit-learn
```

4. Apply database migrations:

```bash
cd maintain
python manage.py migrate
```

5. Start the development server:

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

## Default Access

The application includes organization and admin flows. You can create a new organization account from the registration page, or use the Django admin if needed.

## Notes

- The default Django secret key and development settings are currently enabled for local development.
- Static files and templates are organized under the project’s Django app directories.
- The ML prediction logic is implemented under the app’s ML module and is used when sensor readings are submitted.

## Useful Commands

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## License

This project is for educational and local development use unless otherwise specified by the repository owner.
