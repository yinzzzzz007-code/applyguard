$requestBody = Get-Content -Raw "$PSScriptRoot\workflow-request.json"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/workflow/mock" -ContentType "application/json" -Body $requestBody

