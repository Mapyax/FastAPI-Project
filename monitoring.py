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
            '[PSCustomObject]@{CPU=$cpu; RAM=$ramUsage} | ConvertTo-Json"'
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
