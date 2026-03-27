# functions that will be used in streamlit_app.py :))

# get_status() for /machines endpoint
# get_machine_history(id) that will be used for /machines/{id}/history endpoint
# save_report(report) for /report endpoint
# create_notification for /notifications endpoint

# if ypu want you can change the signatures 

from src.db_middleware import fetch_machines, insert_report