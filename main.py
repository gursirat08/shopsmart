from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from scraper import search_amazon, search_flipkart
import sqlite3
from datetime import datetime
import pandas as pd
from prophet import Prophet
import plotly.graph_objs as go
from plotly.offline import plot

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="sirat123")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


#  Create DB table
def create_table():
    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            price TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


create_table()


#  Home Page – Landing
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if request.session.get("user"):
        return templates.TemplateResponse("dashboard.html",
                                          {"request": request})
    else:
        return templates.TemplateResponse("home.html", {"request": request})


#  Dashboard (Main App) – behind login
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": None
    })


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "results": None
    })


#  Search
@app.post("/search", response_class=HTMLResponse)
def search(request: Request, product: str = Form(...)):
    if not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=303)

    product_key = product.strip().lower()
    amazon_results = search_amazon(product)
    flipkart_results = search_flipkart(product)

    for r in amazon_results + flipkart_results:
        r["key"] = product_key

    combined = amazon_results + flipkart_results

    for item in combined:
        price = item.get("price", "")
        if price.startswith("₹") and any(char.isdigit() for char in price):
            conn = sqlite3.connect("searches.db")
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO searches (product, price, timestamp) VALUES (?, ?, ?)",
                (product_key, price,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            break

    return templates.TemplateResponse("index.html", {
        "request": request,
        "results": combined
    })


#  Forecast
@app.get("/forecast/{product_key}", response_class=HTMLResponse)
def forecast_price(request: Request, product_key: str):
    if not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=303)

    conn = sqlite3.connect("searches.db")
    try:
        df = pd.read_sql_query(
            "SELECT timestamp, price FROM searches WHERE product = ?",
            conn,
            params=(product_key, ))
    except Exception as e:
        print("❌ DB Error:", e)
        df = pd.DataFrame()
    conn.close()

    df = df[df["price"].str.contains("₹")]
    df["ds"] = pd.to_datetime(df["timestamp"])
    df["y"] = df["price"].str.replace("₹", "").str.replace(",",
                                                           "").astype(float)

    if df.empty or len(df) < 3:
        return templates.TemplateResponse("not_enough_data.html",
                                          {"request": request})

    model = Prophet()
    model.fit(df[["ds", "y"]])
    future = model.make_future_dataframe(periods=7)
    forecast = model.predict(future)

    trace1 = go.Scatter(x=df["ds"],
                        y=df["y"],
                        mode='lines+markers',
                        name="Actual")
    trace2 = go.Scatter(x=forecast["ds"],
                        y=forecast["yhat"],
                        mode='lines',
                        name="Forecast")

    layout = go.Layout(title="Price Forecast",
                       xaxis_title="Date",
                       yaxis_title="Price (₹)",
                       template="plotly_white")
    fig = go.Figure(data=[trace1, trace2], layout=layout)
    chart_html = plot(fig, output_type="div", include_plotlyjs=True)

    current = df["y"].iloc[-1]
    future_price = forecast["yhat"].iloc[-1]

    if future_price > current:
        decision = "✅ Buy Now: Price may rise"
    elif future_price < current:
        decision = "⏳ Wait: Price expected to drop"
    else:
        decision = "ℹ️ Price is stable"

    return templates.TemplateResponse(
        "forecast.html", {
            "request": request,
            "product": product_key,
            "chart": chart_html,
            "decision": decision
        })


#  History page
@app.get("/history", response_class=HTMLResponse)
def view_history(request: Request):
    if not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=303)

    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT product, price, timestamp FROM searches ORDER BY timestamp DESC LIMIT 20"
    )
    rows = cur.fetchall()
    conn.close()

    return templates.TemplateResponse("history.html", {
        "request": request,
        "rows": rows
    })


#  Login
@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })


@app.post("/login", response_class=HTMLResponse)
def login_post(request: Request,
               username: str = Form(...),
               password: str = Form(...)):
    if username == "sirat" and password == "sirat123":
        request.session["user"] = username
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid credentials"
        })


#  Logout
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
