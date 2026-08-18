"""FastAPI Demo Bank Application simulating legacy back-office UI."""
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, Response, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.demo_bank.models import MEMBERS_DB, Member, GLOBAL_FAULT_STATE, FaultInjectionState

app = FastAPI(title="Demo Legacy Bank Back-Office")

def render_base_layout(title: str, body_content: str, request: Request) -> str:
    """Render standard back-office HTML layout with legacy styling and optional injected dialogs."""
    dialog_html = ""
    if GLOBAL_FAULT_STATE.unexpected_dialog:
        dialog_html = """
        <div id="unexpected-dialog-overlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;display:flex;align-items:center;justify-content:center;">
            <div style="background:#fff;padding:24px;border:2px solid #cc0000;border-radius:6px;max-width:450px;box-shadow:0 4px 12px rgba(0,0,0,0.3);text-align:center;">
                <h3 style="color:#cc0000;margin-top:0;">System Maintenance Alert</h3>
                <p>Scheduled maintenance is in progress. Some features may be unavailable.</p>
                <button id="dismiss-dialog-btn" onclick="document.getElementById('unexpected-dialog-overlay').style.display='none';" style="padding:8px 16px;background:#333;color:#fff;border:none;border-radius:4px;cursor:pointer;">Dismiss Notice</button>
            </div>
        </div>
        """

    session_banner = ""
    session_id = request.cookies.get("session_id")
    if session_id:
        session_banner = f'<div style="float:right;font-size:12px;color:#666;">Logged in as: <strong>operator</strong> | <a href="/logout">Logout</a></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title} - Legacy Bank Back-Office</title>
    <style>
        body {{ font-family: Arial, Helvetica, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; color: #222; }}
        .header {{ background-color: #1a365d; color: white; padding: 15px 20px; border-radius: 4px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; font-size: 20px; text-transform: uppercase; letter-spacing: 1px; display: inline-block; }}
        .container {{ background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 25px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; font-weight: bold; margin-bottom: 5px; font-size: 14px; color: #334155; }}
        input[type="text"], input[type="password"], input[type="number"], select {{ width: 100%; max-width: 400px; padding: 8px 12px; border: 1px solid #94a3b8; border-radius: 4px; font-size: 14px; box-sizing: border-box; }}
        button, .btn {{ background-color: #2563eb; color: white; border: none; padding: 9px 18px; border-radius: 4px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-block; font-size: 14px; }}
        button:hover, .btn:hover {{ background-color: #1d4ed8; }}
        .btn-secondary {{ background-color: #64748b; }}
        .btn-secondary:hover {{ background-color: #475569; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        .table th, .table td {{ border: 1px solid #cbd5e1; padding: 10px 14px; text-align: left; font-size: 14px; }}
        .table th {{ background-color: #f1f5f9; color: #1e293b; font-weight: bold; }}
        .alert {{ padding: 12px 16px; border-radius: 4px; margin-bottom: 20px; font-weight: bold; }}
        .alert-error {{ background-color: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }}
        .alert-info {{ background-color: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }}
        .card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin-bottom: 15px; background: #fafafa; }}
    </style>
</head>
<body>
    {dialog_html}
    <div class="header">
        <h1>Legacy Federal Credit Union - Core Banking System</h1>
        {session_banner}
    </div>
    <div class="container">
        {body_content}
    </div>
</body>
</html>"""

def check_faults_and_auth(request: Request) -> Optional[Response]:
    """Helper to evaluate active fault states and auth cookies."""
    if GLOBAL_FAULT_STATE.application_error:
        return HTMLResponse(
            status_code=500,
            content=render_base_layout(
                "500 Internal Error",
                '<div class="alert alert-error"><h2>APPLICATION_ERROR</h2><p>500 Internal Server Error: Banking Core Service Unreachable</p></div>',
                request
            )
        )
    
    if GLOBAL_FAULT_STATE.session_timeout:
        return RedirectResponse(url="/login?expired=1", status_code=303)
        
    return None

@app.get("/")
def index(request: Request):
    return RedirectResponse(url="/members", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def get_login(request: Request, expired: int = 0):
    banner = ""
    if expired or GLOBAL_FAULT_STATE.session_timeout:
        banner = '<div class="alert alert-error" id="session-timeout-banner">SESSION_TIMEOUT: Your session has expired or is invalid. Please log in again.</div>'
    
    body = f"""
    <h2>Operator Authentication</h2>
    {banner}
    <div class="card" style="max-width: 450px;">
        <form action="/login" method="post" id="login-form">
            <div class="form-group">
                <label for="username_input">Operator Username</label>
                <input type="text" id="username_input" name="username" value="operator" required>
            </div>
            <div class="form-group">
                <label for="password_input">Password</label>
                <input type="password" id="password_input" name="password" value="password123" required>
            </div>
            <button type="submit" id="btn-login-submit">Sign In to Workstation</button>
        </form>
    </div>
    """
    return render_base_layout("Operator Login", body, request)

@app.post("/login")
def post_login(username: str = Form(...), password: str = Form(...)):
    response = RedirectResponse(url="/members", status_code=303)
    response.set_cookie(key="session_id", value="valid_operator_session_987", httponly=True)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_id")
    return response

@app.get("/members", response_class=HTMLResponse)
async def get_members(request: Request, search_id: Optional[str] = None):
    fault_res = check_faults_and_auth(request)
    if fault_res:
        return fault_res

    if GLOBAL_FAULT_STATE.transient_load_failure:
        await asyncio.sleep(2.5)

    error_html = ""
    matched_members = list(MEMBERS_DB.values())

    if search_id:
        if search_id == "99999" or search_id not in MEMBERS_DB:
            error_html = f'<div class="alert alert-error" id="member-not-found-banner">MEMBER_NOT_FOUND: Member ID "{search_id}" not found in database.</div>'
            matched_members = []
        else:
            matched_members = [MEMBERS_DB[search_id]]

    rows = ""
    for m in matched_members:
        rows += f"""
        <tr>
            <td>{m.member_id}</td>
            <td>{m.name}</td>
            <td>${m.savings_balance:,.2f} {m.currency}</td>
            <td>${m.checking_balance:,.2f} {m.currency}</td>
            <td><span style="color:green;font-weight:bold;">{m.status}</span></td>
            <td><a href="/members/{m.member_id}" class="btn" id="view-member-{m.member_id}">View Details & Accounts</a></td>
        </tr>
        """

    body = f"""
    <h2>Member Management & Lookup</h2>
    {error_html}
    <div class="card">
        <form action="/members" method="get" id="member-search-form">
            <div class="form-group">
                <label for="search_member_id_input">Search by Member ID</label>
                <input type="text" id="search_member_id_input" name="search_id" value="{search_id or ''}" placeholder="Enter Member ID (e.g. 12345)">
            </div>
            <button type="submit" id="btn-search-member">Search Member</button>
            <a href="/members" class="btn btn-secondary">Clear Search</a>
        </form>
    </div>
    
    <h3>Member Directory Results</h3>
    <table class="table" id="members-table">
        <thead>
            <tr>
                <th>Member ID</th>
                <th>Full Name</th>
                <th>Savings Balance</th>
                <th>Checking Balance</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {rows if rows else '<tr><td colspan="6">No members found matching criteria.</td></tr>'}
        </tbody>
    </table>
    """
    return render_base_layout("Member Directory", body, request)

@app.get("/members/{member_id}", response_class=HTMLResponse)
async def get_member_detail(member_id: str, request: Request):
    fault_res = check_faults_and_auth(request)
    if fault_res:
        return fault_res

    if member_id == "99999" or member_id not in MEMBERS_DB:
        body = f"""
        <div class="alert alert-error" id="member-not-found-banner">
            <h3>MEMBER_NOT_FOUND</h3>
            <p>Member ID <strong>{member_id}</strong> does not exist in the banking records.</p>
        </div>
        <a href="/members" class="btn btn-secondary">Back to Member Search</a>
        """
        return HTMLResponse(status_code=404, content=render_base_layout("Member Not Found", body, request))

    member = MEMBERS_DB[member_id]
    body = f"""
    <div style="margin-bottom:15px;">
        <a href="/members" class="btn btn-secondary">&laquo; Back to Member Search</a>
    </div>
    <h2>Member Account Details - {member.name} (ID: {member.member_id})</h2>
    
    <div class="card" id="member-summary-card">
        <h3>Summary Information</h3>
        <table class="table" style="max-width: 600px;">
            <tr><th>Member ID</th><td id="val-member-id">{member.member_id}</td></tr>
            <tr><th>Full Name</th><td id="val-member-name">{member.name}</td></tr>
            <tr><th>Primary Savings Balance</th><td id="val-savings-balance">${member.savings_balance:,.2f} {member.currency}</td></tr>
            <tr><th>Checking Balance</th><td id="val-checking-balance">${member.checking_balance:,.2f} {member.currency}</td></tr>
            <tr><th>Status</th><td>{member.status}</td></tr>
        </table>
    </div>

    <div style="margin-top: 20px;">
        <a href="/members/{member.member_id}/subaccounts/new" class="btn" id="btn-open-new-subaccount">Open New Sub-Account</a>
    </div>
    """
    return render_base_layout(f"Member Details {member.member_id}", body, request)

@app.get("/members/{member_id}/subaccounts/new", response_class=HTMLResponse)
def get_new_subaccount_form(member_id: str, request: Request, validation_error: int = 0):
    fault_res = check_faults_and_auth(request)
    if fault_res:
        return fault_res

    if member_id not in MEMBERS_DB:
        raise HTTPException(status_code=404, detail="Member not found")

    member = MEMBERS_DB[member_id]
    error_banner = ""
    if validation_error or GLOBAL_FAULT_STATE.validation_error:
        error_banner = '<div class="alert alert-error" id="validation-error-banner">VALIDATION_ERROR: Sub-account name must be at least 3 characters and initial deposit must be positive.</div>'

    body = f"""
    <h2>Open New Sub-Account for {member.name} ({member.member_id})</h2>
    {error_banner}
    <div class="card" style="max-width: 550px;">
        <form action="/members/{member.member_id}/subaccounts/new" method="post" id="new-subaccount-form">
            <div class="form-group">
                <label for="account_type_select">Sub-Account Type</label>
                <select id="account_type_select" name="account_type">
                    <option value="High-Yield Savings">High-Yield Savings</option>
                    <option value="Money Market">Money Market Savings</option>
                    <option value="Vacation Fund">Vacation Savings</option>
                </select>
            </div>
            <div class="form-group">
                <label for="subaccount_name_input">Sub-Account Label / Custom Name</label>
                <input type="text" id="subaccount_name_input" name="subaccount_name" value="Secondary Savings" placeholder="e.g. Emergency Fund">
            </div>
            <div class="form-group">
                <label for="initial_deposit_input">Initial Deposit Amount ($)</label>
                <input type="number" id="initial_deposit_input" name="initial_deposit" value="500.00" step="0.01">
            </div>
            <div style="background:#fffbe0;border:1px solid #ffe58f;padding:10px;margin-bottom:15px;border-radius:4px;font-size:12px;color:#873800;">
                <strong>Notice:</strong> Opening a new sub-account is a financial transaction requiring confirmation.
            </div>
            <button type="submit" id="btn-submit-create-subaccount" name="submit_action" value="create">Submit & Create Sub-Account</button>
            <a href="/members/{member.member_id}" class="btn btn-secondary">Cancel</a>
        </form>
    </div>
    """
    return render_base_layout("New Sub-Account", body, request)

@app.post("/members/{member_id}/subaccounts/new")
def post_new_subaccount(
    member_id: str,
    request: Request,
    account_type: str = Form(...),
    subaccount_name: str = Form(...),
    initial_deposit: float = Form(...)
):
    fault_res = check_faults_and_auth(request)
    if fault_res:
        return fault_res

    if GLOBAL_FAULT_STATE.validation_error or len(subaccount_name.strip()) < 3 or initial_deposit <= 0:
        body = f"""
        <h2>Open New Sub-Account for Member {member_id}</h2>
        <div class="alert alert-error" id="validation-error-banner">VALIDATION_ERROR: Sub-account name must be at least 3 characters and initial deposit must be positive.</div>
        <a href="/members/{member_id}/subaccounts/new" class="btn btn-secondary">Back to Form</a>
        """
        return HTMLResponse(status_code=422, content=render_base_layout("Validation Error", body, request))

    redirect_url = f"/members/{member_id}/subaccounts/confirmation?type={account_type}&name={subaccount_name}&deposit={initial_deposit}"
    return RedirectResponse(url=redirect_url, status_code=303)

@app.get("/members/{member_id}/subaccounts/confirmation", response_class=HTMLResponse)
def get_subaccount_confirmation(
    member_id: str,
    request: Request,
    type: str = "High-Yield Savings",
    name: str = "Secondary Savings",
    deposit: float = 500.00
):
    fault_res = check_faults_and_auth(request)
    if fault_res:
        return fault_res

    member = MEMBERS_DB.get(member_id, Member(member_id=member_id, name="Jane Doe", savings_balance=12450.32))

    body = f"""
    <div class="alert alert-info" style="background:#f0fdf4;border-color:#bbf7d0;color:#166534;" id="confirmation-success-banner">
        <h2>Sub-Account Opened Successfully!</h2>
        <p>Confirmation Ref: <strong>SUB-{member_id}-9942</strong></p>
    </div>
    
    <div class="card" id="confirmation-details-card">
        <h3>Sub-Account Summary</h3>
        <table class="table" style="max-width: 500px;">
            <tr><th>Member ID</th><td id="confirm-member-id">{member.member_id}</td></tr>
            <tr><th>Member Name</th><td id="confirm-member-name">{member.name}</td></tr>
            <tr><th>Sub-Account Type</th><td id="confirm-account-type">{type}</td></tr>
            <tr><th>Custom Label</th><td id="confirm-account-name">{name}</td></tr>
            <tr><th>Initial Deposit</th><td id="confirm-deposit">${deposit:,.2f} USD</td></tr>
            <tr><th>Status</th><td><strong style="color:green;" id="confirm-status">CONFIRMED / ACTIVE</strong></td></tr>
        </table>
    </div>

    <a href="/members/{member.member_id}" class="btn" id="btn-return-member">Return to Member Profile</a>
    """
    return render_base_layout("Sub-Account Confirmation", body, request)

@app.get("/admin/faults", response_class=HTMLResponse)
def get_faults_admin(request: Request):
    body = f"""
    <h2>Admin - Fault Injection Controls</h2>
    <form action="/admin/faults" method="post">
        <div class="card">
            <label><input type="checkbox" name="session_timeout" {'checked' if GLOBAL_FAULT_STATE.session_timeout else ''}> Inject SESSION_TIMEOUT</label><br>
            <label><input type="checkbox" name="unexpected_dialog" {'checked' if GLOBAL_FAULT_STATE.unexpected_dialog else ''}> Inject UNEXPECTED_DIALOG</label><br>
            <label><input type="checkbox" name="application_error" {'checked' if GLOBAL_FAULT_STATE.application_error else ''}> Inject APPLICATION_ERROR (500)</label><br>
            <label><input type="checkbox" name="transient_load_failure" {'checked' if GLOBAL_FAULT_STATE.transient_load_failure else ''}> Inject TRANSIENT_LOAD_FAILURE</label><br>
            <label><input type="checkbox" name="validation_error" {'checked' if GLOBAL_FAULT_STATE.validation_error else ''}> Inject VALIDATION_ERROR</label><br>
        </div>
        <button type="submit">Update Fault State</button>
    </form>
    """
    return render_base_layout("Fault Controls", body, request)

@app.post("/admin/faults")
def post_faults_admin(
    session_timeout: bool = Form(False),
    unexpected_dialog: bool = Form(False),
    application_error: bool = Form(False),
    transient_load_failure: bool = Form(False),
    validation_error: bool = Form(False)
):
    GLOBAL_FAULT_STATE.session_timeout = session_timeout
    GLOBAL_FAULT_STATE.unexpected_dialog = unexpected_dialog
    GLOBAL_FAULT_STATE.application_error = application_error
    GLOBAL_FAULT_STATE.transient_load_failure = transient_load_failure
    GLOBAL_FAULT_STATE.validation_error = validation_error
    return RedirectResponse(url="/admin/faults", status_code=303)

@app.post("/admin/inject-state")
def inject_state_api(faults: FaultInjectionState):
    """API endpoint for automated test runner to inject faults cleanly."""
    GLOBAL_FAULT_STATE.session_timeout = faults.session_timeout
    GLOBAL_FAULT_STATE.unexpected_dialog = faults.unexpected_dialog
    GLOBAL_FAULT_STATE.application_error = faults.application_error
    GLOBAL_FAULT_STATE.transient_load_failure = faults.transient_load_failure
    GLOBAL_FAULT_STATE.validation_error = faults.validation_error
    return {"status": "ok", "current_faults": GLOBAL_FAULT_STATE.model_dump()}
