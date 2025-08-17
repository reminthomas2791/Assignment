from multiprocessing import Value
from optparse import Values
from tkinter.tix import Form
from typing import Optional
from urllib import response
from winreg import QueryInfoKey, QueryReflectionKey, QueryValue, QueryValueEx
import starlette.status as status
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import google.oauth2.id_token
from google.cloud import firestore
from google.auth.transport import requests
from google.cloud.firestore_v1.base_query import FieldFilter


app = FastAPI()

firestore_db = firestore.Client()
firebase_request_adapter = requests.Request()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


def getUser(user_token):
    user = firestore_db.collection("users").document(user_token["user_id"])

    if not user.get().exists:
        user_data = {
            "name": "Remin Thomas",
        }
        firestore_db.collection("users").document(user_token["user_id"]).set(user_data)

    return user


def validateFirebaseToken(id_token):
    if not id_token:
        return None

    user_token = None

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(
            id_token, firebase_request_adapter
        )
    except ValueError as err:
        print(str(err))

    return user_token


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    evs = firestore_db.collection("electric_vandi").stream()
    return templates.TemplateResponse(
        "index.html", {"request": request, "user_token": user_token, "evs": evs}
    )


@app.get("/add-ev/", response_class=HTMLResponse)
async def add_ev(request: Request):
    return templates.TemplateResponse("add-ev.html", {"request": request})


@app.post("/add-ev/", response_class=HTMLResponse)
async def add_ev_post(request: Request):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

    form = await request.form()

    ev_data = {
        "name": form.get("name"),
        "manufacturer": form.get("manufacturer"),
        "year": int(form.get("year")),
        "battery_size": int(form.get("battery_size")),
        "wltp_range": int(form.get("range")),
        "cost": float(form.get("cost")),
        "power": float(form.get("power")),
        "review_list": [],
    }
    firestore_db.collection("electric_vandi").document().set(ev_data)

    return RedirectResponse("/add-ev/", status_code=status.HTTP_302_FOUND)


@app.get("/ev-detail/{ev_id}/", response_class=HTMLResponse)
async def ev_detail(request: Request, ev_id: str):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    ev = firestore_db.collection("electric_vandi").document(ev_id).get()

    return templates.TemplateResponse(
        "ev-detail.html",
        {"request": request, "user_token": user_token, "ev": ev, "ev_id": ev_id},
    )

@app.post("/search-ev/", response_class=HTMLResponse)
async def search_ev(
    request: Request,
    attribute: str = Form(),
    value: str = Form(),
    min_value: int = Form(),
    max_value: int = Form(),
):
    form_data = await request.form()
    attribute = form_data.get("attribute", None)
    text_value = form_data.get("text_value", None)
    
    min_value = int(form_data.get("min_value")) if form_data.get("min_value") and form_data.get("min_value").strip() else None
    max_value = int(form_data.get("max_value")) if form_data.get("max_value") and form_data.get("max_value").strip() else None

    # Construct query based on the selected attribute and value/range
    query = firestore_db.collection("electric_vandi")
    if text_value:
        query = query.where(attribute, "==", text_value)
    elif min_value is not None and max_value is not None:
        query = query.where(attribute, ">=", min_value).where(attribute, "<=", max_value)
    
    
    # Execute the query and retrieve the documents
    evs = query.stream()

    return templates.TemplateResponse("index.html", {"request": request, "evs": evs})

@app.post("/ev-detail/{ev_id}/edit")
async def edit_ev_details(ev_id: str, request: Request):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    form_data = await request.form()
    
    # Retrieve the electric vehicle document from Firestore
    ev_ref = firestore_db.collection("electric_vandi").document(ev_id)
    ev_doc = ev_ref.get()
    ev_ref.update({
        "name": (form_data.get("name")),
        "manufacturer": form_data.get("manufacturer"),
        "year": (form_data.get("year")),
        "battery_size": (form_data.get("battery_size")),
        "wltp_range": (form_data.get("wltp_range")),
        "cost": (form_data.get("cost")),
        "power":(form_data.get("power"))
    })
    
    return RedirectResponse(f"/ev-detail/{ev_id}/", status_code=status.HTTP_302_FOUND)


@app.post("/ev-detail/{ev_id}/delete")
async def delete_ev(ev_id: str, request: Request):
    id_token = request.cookies.get("token")
    user_token = validateFirebaseToken(id_token)

    if not user_token:
        return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
    
    # Retrieve the electric vehicle document from Firestore
    firestore_db.collection("electric_vandi").document(ev_id).delete()
    
    return RedirectResponse(f"/", status_code=status.HTTP_302_FOUND)

@app.get("/compare-evs/", response_class=HTMLResponse)
async def compare_evs_get(request: Request):
    evs = firestore_db.collection("electric_vandi").stream()
    #evs = [ev for ev in evs_snapshot]
    return templates.TemplateResponse("ev-compare.html", {"request": request, "evs": list(evs)})

@app.post("/compare-evs/", response_class=HTMLResponse)
async def compare_evs_post(request: Request, ev1: str = Form(), ev2: str = Form()):
    try:
        ev1_details = firestore_db.collection("electric_vandi").document(ev1).get().to_dict()
        ev2_details = firestore_db.collection("electric_vandi").document(ev2).get().to_dict()
        
    except Exception as e:
        raise HTTPException(status_code=404, detail="One or more selected EVs not found")

    return templates.TemplateResponse("ev-compare.html", {"request": request, "ev1": ev1_details, "ev2": ev2_details, "ev1_id": ev1, "ev2_id": ev2 })



