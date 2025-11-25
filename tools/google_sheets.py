"""
Google Sheets integration tool.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False


class GoogleSheetsAPI:
    """
    Google Sheets API client for writing recommendations and tracking data.
    
    Handles:
    - Auto-creating sheets if they don't exist
    - Writing recommendations
    - Reading pending recommendations
    - Error handling
    """
    
    def __init__(self, credentials_path: str, sheet_id: Optional[str] = None):
        """
        Initialize Google Sheets API client.
        
        Args:
            credentials_path: Path to service account JSON file
            sheet_id: Google Sheets ID (optional, can be set later)
        """
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError(
                "Google Sheets API not available. "
                "Install with: pip install google-api-python-client google-auth"
            )
        
        self.credentials_path = Path(credentials_path)
        self.sheet_id = sheet_id
        self.service = None
        
        if self.credentials_path.exists():
            self._initialize_service()
    
    def _initialize_service(self) -> None:
        """Initialize Google Sheets service."""
        try:
            creds = service_account.Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=creds)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google Sheets service: {str(e)}")
    
    def create_sheet_if_not_exists(
        self,
        sheet_name: str = "Feedback",
        headers: Optional[List[str]] = None
    ) -> str:
        """
        Create a new Google Sheet if sheet_id is not set.
        
        Args:
            sheet_name: Name for the new sheet
            headers: Headers for the first row
            
        Returns:
            Created sheet ID
        """
        if not self.service:
            raise RuntimeError("Google Sheets service not initialized")
        
        if self.sheet_id:
            # Sheet ID already exists, just ensure the worksheet exists
            self._ensure_worksheet_exists(sheet_name, headers)
            return self.sheet_id
        
        # Create new spreadsheet
        try:
            spreadsheet = {
                'properties': {
                    'title': 'Prospect Campaign Feedback'
                },
                'sheets': [{
                    'properties': {
                        'title': sheet_name
                    }
                }]
            }
            
            spreadsheet = self.service.spreadsheets().create(body=spreadsheet).execute()
            self.sheet_id = spreadsheet['spreadsheetId']
            
            # Add headers if provided
            if headers:
                self.write_row(sheet_name, headers, row=1)
            
            return self.sheet_id
            
        except HttpError as e:
            raise RuntimeError(f"Failed to create Google Sheet: {str(e)}")
    
    def _ensure_worksheet_exists(
        self,
        worksheet_name: str,
        headers: Optional[List[str]] = None
    ) -> None:
        """
        Ensure a worksheet exists in the spreadsheet.
        
        Args:
            worksheet_name: Name of the worksheet
            headers: Headers to add if worksheet is new
        """
        if not self.sheet_id:
            return
        
        try:
            # Get spreadsheet metadata
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.sheet_id
            ).execute()
            
            # Check if worksheet exists
            worksheet_exists = any(
                sheet['properties']['title'] == worksheet_name
                for sheet in spreadsheet.get('sheets', [])
            )
            
            if not worksheet_exists:
                # Create new worksheet
                requests = [{
                    'addSheet': {
                        'properties': {
                            'title': worksheet_name
                        }
                    }
                }]
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={'requests': requests}
                ).execute()
                
                # Add headers if provided
                if headers:
                    self.write_row(worksheet_name, headers, row=1)
            
        except HttpError as e:
            raise RuntimeError(f"Failed to ensure worksheet exists: {str(e)}")
    
    def write_row(
        self,
        worksheet_name: str,
        values: List[Any],
        row: Optional[int] = None
    ) -> None:
        """
        Write a row to the sheet.
        
        Args:
            worksheet_name: Name of the worksheet
            values: List of values to write
            row: Row number (if None, appends to end)
        """
        if not self.service or not self.sheet_id:
            raise RuntimeError("Google Sheets not initialized")
        
        try:
            range_name = f"{worksheet_name}!A{row}" if row else f"{worksheet_name}!A:A"
            
            body = {
                'values': [values]
            }
            
            if row:
                # Update specific row
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body=body
                ).execute()
            else:
                # Append to end
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body=body
                ).execute()
                
        except HttpError as e:
            raise RuntimeError(f"Failed to write to Google Sheet: {str(e)}")
    
    def write_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        worksheet_name: str = "Feedback",
        run_id: Optional[str] = None
    ) -> None:
        """
        Write recommendations to Google Sheets.
        
        Args:
            recommendations: List of recommendation dictionaries
            worksheet_name: Name of the worksheet
            run_id: Optional run ID
        """
        if not recommendations:
            return
        
        # Ensure worksheet exists with headers
        headers = ["Run ID", "Field", "Old Value", "New Value", "Reason", "Status", "Created At"]
        self._ensure_worksheet_exists(worksheet_name, headers)
        
        # Clear existing data (optional - or append)
        # For now, we'll append to preserve history
        
        # Write recommendations
        from datetime import datetime
        for rec in recommendations:
            row = [
                run_id or "",
                rec.get("field", ""),
                json.dumps(rec.get("old_value", "")),
                json.dumps(rec.get("new_value", "")),
                rec.get("reason", ""),
                "Pending",
                datetime.utcnow().isoformat()
            ]
            self.write_row(worksheet_name, row)
    
    def read_pending_recommendations(
        self,
        worksheet_name: str = "Feedback"
    ) -> List[Dict[str, Any]]:
        """
        Read pending recommendations from Google Sheets.
        
        Args:
            worksheet_name: Name of the worksheet
            
        Returns:
            List of recommendation dictionaries
        """
        if not self.service or not self.sheet_id:
            return []
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{worksheet_name}!A:G"
            ).execute()
            
            values = result.get('values', [])
            if len(values) < 2:  # No data rows (only headers)
                return []
            
            headers = values[0]
            recommendations = []
            
            for row in values[1:]:
                if len(row) < 6:
                    continue
                
                # Check if status is "Pending"
                status = row[5] if len(row) > 5 else ""
                if status.lower() != "pending":
                    continue
                
                rec = {
                    "run_id": row[0] if len(row) > 0 else "",
                    "field": row[1] if len(row) > 1 else "",
                    "old_value": json.loads(row[2]) if len(row) > 2 and row[2] else None,
                    "new_value": json.loads(row[3]) if len(row) > 3 and row[3] else None,
                    "reason": row[4] if len(row) > 4 else "",
                    "status": status,
                    "created_at": row[6] if len(row) > 6 else ""
                }
                recommendations.append(rec)
            
            return recommendations
            
        except HttpError as e:
            raise RuntimeError(f"Failed to read from Google Sheet: {str(e)}")
    
    def update_recommendation_status(
        self,
        field: str,
        old_value: Any,
        new_value: Any,
        worksheet_name: str = "Feedback",
        status: str = "Approved"
    ) -> None:
        """
        Update recommendation status in Google Sheets.
        
        Args:
            field: Field name
            old_value: Old value
            new_value: New value
            worksheet_name: Name of the worksheet
            status: New status (default: "Approved")
        """
        if not self.service or not self.sheet_id:
            return
        
        try:
            # Find the row with matching field, old_value, and new_value
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{worksheet_name}!A:G"
            ).execute()
            
            values = result.get('values', [])
            
            for idx, row in enumerate(values[1:], start=2):  # Start from row 2 (after headers)
                if len(row) < 6:
                    continue
                
                if (row[1] == field and 
                    row[2] == json.dumps(old_value) and 
                    row[3] == json.dumps(new_value) and
                    row[5].lower() == "pending"):
                    
                    # Update status
                    from datetime import datetime
                    range_name = f"{worksheet_name}!F{idx}"
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.sheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body={'values': [[status, datetime.utcnow().isoformat()]]}
                    ).execute()
                    break
                    
        except HttpError as e:
            raise RuntimeError(f"Failed to update Google Sheet: {str(e)}")

