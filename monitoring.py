import subprocess
import json

def get_system_metrics():
    """returns CPU and RAM usage in %"""
    try:
        power_shell_cmd = (
            'powershell -Command "'
            '$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; '
            '$os = Get-CimInstance Win32_OperatingSystem; '
            '$totalRam = $os.TotalVisibleMemorySize; '
            '$freeRam = $os.FreePhysicalMemory; '
            '$ramUsage = [Math]::Round((($totalRam - $freeRam) / $totalRam) * 100, 1); '
            '$uptime = [Math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 2); '
            '$disk = Get-CimInstance Win32_LogicalDisk -Filter \\"DeviceID=\'C:\'\\"; '
            '$diskTotal = [Math]::Round($disk.Size / 1GB, 1); '
            '$diskFree = [Math]::Round($disk.FreeSpace / 1GB, 1); '
            '$procCount = (Get-Process).Count; '
            '$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; '
            '$batPercent = if ($battery) { $battery.EstimatedChargeRemaining } else { -1 }; '
            
            '[PSCustomObject]@{Uptime_Hours=$uptime; CPU=$cpu; RAM=$ramUsage; Processes=$procCount;'
            'Battery_Percent=$batPercent; Disk_Total_GB=$diskTotal; Disk_Free_GB=$diskFree;} | ConvertTo-Json"'
        )
        
        output = subprocess.check_output(power_shell_cmd, shell=True, text=True, encoding='utf-8')
        
        data = json.loads(output)
        
        return data
        
    except subprocess.CalledProcessError as e:
        print(f"System call error: {e}")
    except Exception as e:
        print(f"Error occured: {e}")

# cpu, ram = get_system_metrics()
# print(cpu, ram)
