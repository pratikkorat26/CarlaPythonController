let currentRobot = null;
const telemetryLog = [];
let eventSource = null;
let reconnectTimeout = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_INTERVAL = 3000;


// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    fetchRobots();
    initSpeedChart();
});

// Robot Management Functions
function fetchRobots() {
    fetch('/robots')
        .then(response => response.json())
        .then(data => {
            updateRobotList(data.robots);
        })
        .catch(error => {
            console.error("Error fetching robots:", error);
        });
}

function updateRobotList(robots) {
    const robotList = document.getElementById('robot-list');

    if (robots.length === 0) {
        robotList.innerHTML = '<div class="no-robots-msg">No robots available. Create one to begin.</div>';
        setControlsEnabled(false);
        return;
    }

    robotList.innerHTML = '';

    robots.forEach(robotId => {
        const robotElement = document.createElement('div');
        robotElement.className = 'robot-item' + (robotId === currentRobot ? ' active' : '');

        robotElement.innerHTML = `
            <div>${robotId}</div>
            <div>
                <button onclick="selectRobot('${robotId}')">Select</button>
                <button class="stop" onclick="deleteRobot('${robotId}')">Delete</button>
            </div>
        `;
        robotList.appendChild(robotElement);
    });

    // Auto-select the first robot if none is selected
    if (!currentRobot && robots.length > 0) {
        selectRobot(robots[0]);
    }
}


function createRobot() {
    const robotIdInput = document.getElementById('robot-id-input');
    const robotId = robotIdInput.value.trim();

    if (!robotId) {
        alert("Please enter a robot ID");
        return;
    }

    fetch(`/robots/${robotId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        logMessage(`Robot created: ${data.message}`);
        robotIdInput.value = '';

        // ✅ Immediately select the new robot
        selectRobot(robotId);

        // ✅ Update robot list in the UI
        fetchRobots();
    })
    .catch(error => {
        console.error("Error creating robot:", error);
        logMessage(`Error creating robot: ${error.message}`, true);
    });
}


function deleteRobot(robotId) {
    if (confirm(`Are you sure you want to delete robot "${robotId}"?`)) {
        fetch(`/robots/${robotId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            logMessage(`Robot deleted: ${data.message}`);
            if (currentRobot === robotId) {
                currentRobot = null;
                closeSSE();
                resetUI();
            }
            fetchRobots();
        })
        .catch(error => {
            console.error("Error deleting robot:", error);
            logMessage(`Error deleting robot: ${error.message}`, true);
        });
    }
}

function selectRobot(robotId) {
    // Close SSE and reset UI if switching robots
    if (currentRobot && currentRobot !== robotId) {
        closeSSE();
        resetUI();
    }

    // ✅ Set the selected robot FIRST
    currentRobot = robotId;
    setControlsEnabled(true);
    logMessage(`Selected robot: ${robotId}`);

    // ✅ Update stream image
    const img = document.getElementById("stream");
    if (img) {
        img.src = `/robots/${robotId}/video_feed?t=${Date.now()}`; // optional cache-busting
    }

    // ✅ Now update the robot list to visually reflect selection
    fetchRobots();
}

function setControlsEnabled(enabled) {
    const controlContainer = document.getElementById('control-container');
    if (enabled) {
        controlContainer.classList.remove('disabled');
    } else {
        controlContainer.classList.add('disabled');
    }
}

function resetUI() {
    resetDataValues();
    clearTelemetry();
    const img = document.getElementById("stream");
    img.src = '';
}

// Vehicle Control Functions
function spawn() {
    const x = parseFloat(document.getElementById("dx_in").value);
    const y = parseFloat(document.getElementById("dy_in").value);
    const z = parseFloat(document.getElementById("dz_in").value);

    fetch(`/robots/${currentRobot}/spawn?x=${x}&y=${y}&z=${z}`, {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        logMessage(`🚗 ${data.message}`);
    })
    .catch(err => console.error("Spawn Error:", err));
}

function destroy() {
    logMessage("Destroying vehicle...");
    fetch(`/robots/${currentRobot}/destroy_vehicle`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Vehicle destroyed: ${data.message}`);
        });
}

function drive() {
    const x = document.getElementById('dx').value || 0;
    const y = document.getElementById('dy').value || 0;
    const z = document.getElementById('dz').value || 0;

    logMessage(`Driving to target (${x}, ${y}, ${z})...`);

    fetch(`/robots/${currentRobot}/start_drive?x=${x}&y=${y}&z=${z}`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Drive initiated: ${data.message}`);
        })
        .catch(error => {
            console.error("Drive Error:", error);
            logMessage(`Drive Error: ${error.message || "Failed to start driving"}`, true);
        });
}

function stopDrive() {
    logMessage("Stopping drive...");
    fetch(`/robots/${currentRobot}/stop_drive`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Drive stopped: ${data.message}`);
        });
}

function startTelemetry() {
    logMessage("Starting telemetry stream...");
    fetch(`/robots/${currentRobot}/start_telemetry`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Telemetry stream started: ${data.message}`);
            startSSE();
        });
}

function stopTelemetry() {
    logMessage("Stopping telemetry stream...");
    fetch(`/robots/${currentRobot}/stop_telemetry`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Telemetry stream stopped: ${data.message}`);
            closeSSE();
        });
}

function clearTelemetry() {
    telemetryLog.length = 0;
    document.getElementById("telemetry").innerText = "";
    resetDataValues();
}

function resetDataValues() {
    document.getElementById("speed-value").innerText = "0 km/h";
    document.getElementById("throttle-value").innerText = "0%";
    document.getElementById("steering-value").innerText = "0°";
    document.getElementById("brake-value").innerText = "0%";
}

function attachCamera() {
    logMessage("Attaching camera...");
    fetch(`/robots/${currentRobot}/attach_camera`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Camera attached: ${data.message}`);
            // Refresh the image src to ensure we get the latest stream
            const img = document.getElementById("stream");
            img.src = `/robots/${currentRobot}/video_feed?t=${new Date().getTime()}`;
        });
}

function detachCamera() {
    logMessage("Detaching camera...");
    fetch(`/robots/${currentRobot}/detach_camera`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Camera detached: ${data.message}`);
        });
}

function startVideo() {
    logMessage("Starting video stream...");
    fetch(`/robots/${currentRobot}/start_streaming`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Video started: ${data.message}`);
            const img = document.getElementById("stream");
            img.src = `/robots/${currentRobot}/video_feed?t=${new Date().getTime()}`;
        });
}

function stopVideo() {
    logMessage("Stopping video stream...");
    fetch(`/robots/${currentRobot}/stop_streaming`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`Video stopped: ${data.message}`);
        });
}

function startDetection() {
    logMessage("Starting YOLO detection...");
    fetch(`/robots/${currentRobot}/start_detection`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`YOLO detection started: ${data.message}`);
        });
}

function stopDetection() {
    logMessage("Stopping YOLO detection...");
    fetch(`/robots/${currentRobot}/stop_detection`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            logMessage(`YOLO detection stopped: ${data.message}`);
        });
}

// Telemetry and Logging Functions
function logMessage(message, isError = false) {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = isError ? "ERROR" : "INFO";
    const entry = `[${timestamp}] [${prefix}] ${message}`;
    telemetryLog.push(entry);

    // Keep only the last 50 entries
    if (telemetryLog.length > 50) {
        telemetryLog.shift();
    }

    document.getElementById("telemetry").innerText = telemetryLog.join('\n');

    // Auto-scroll to bottom
    const container = document.getElementById("telemetry-container");
    container.scrollTop = container.scrollHeight;
}

function updateSSEStatus(connected) {
    const statusEl = document.getElementById("sse-status");
    if (connected) {
        statusEl.className = "telemetry-status connected";
        statusEl.innerText = "Connected";
    } else {
        statusEl.className = "telemetry-status disconnected";
        statusEl.innerText = "Disconnected";
    }
}

function closeSSE() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }

    reconnectAttempts = 0;
    updateSSEStatus(false);
}

function updateDataDisplay(data) {
    try {
        const telemetryData = JSON.parse(data);
        if (telemetryData.speed !== undefined) {
            const speedKmH = Math.round(telemetryData.speed);
            document.getElementById("speed-value").innerText = `${speedKmH} km/h`;
            updateSpeedChart(speedKmH);
        }

        if (telemetryData.throttle !== undefined) {
            document.getElementById("throttle-value").innerText =
                `${Math.round(telemetryData.throttle * 100)}%`;
        }

        if (telemetryData.steering !== undefined) {
            document.getElementById("steering-value").innerText =
                `${Math.round(telemetryData.steering * 70)}°`;
        }

        if (telemetryData.brake !== undefined) {
            document.getElementById("brake-value").innerText =
                `${Math.round(telemetryData.brake * 100)}%`;
        }
    } catch (e) {
        console.warn("Failed to parse telemetry data:", e);
    }
}

function startSSE() {
    // Close any existing connection
    closeSSE();
    
    if (!currentRobot) {
        logMessage("Cannot start SSE: No robot selected", true);
        return;
    }

    eventSource = new EventSource(`/robots/${currentRobot}/stream_data`);
    updateSSEStatus(true);
    reconnectAttempts = 0;

    eventSource.onmessage = function(event) {
        const timestamp = new Date().toLocaleTimeString();
        const entry = `[${timestamp}] [DATA] ${event.data}`;

        telemetryLog.push(entry);

        // Keep only the last 50 entries
        if (telemetryLog.length > 50) {
            telemetryLog.shift();
        }

        document.getElementById("telemetry").innerText = telemetryLog.join('\n');

        // Auto-scroll to bottom
        const container = document.getElementById("telemetry-container");
        container.scrollTop = container.scrollHeight;

        // Update the live data visualization
        updateDataDisplay(event.data);
    };

    eventSource.onopen = function() {
        updateSSEStatus(true);
        logMessage("SSE connection established");
        reconnectAttempts = 0;
    };

    eventSource.onerror = function(error) {
        console.error("SSE Error:", error);
        eventSource.close();
        eventSource = null;
        updateSSEStatus(false);

        // Only attempt to reconnect if we haven't exceeded the maximum attempts
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            logMessage(`SSE connection lost. Reconnecting (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);

            reconnectTimeout = setTimeout(() => {
                startSSE();
            }, RECONNECT_INTERVAL);
        } else {
            logMessage("Failed to establish SSE connection after multiple attempts", true);
        }
    };
}

// Chart Functions
let speedChart = null;

function initSpeedChart() {
    const ctx = document.getElementById('speedChart').getContext('2d');
    speedChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Speed (km/h)',
                data: [],
                borderColor: '#3498db',
                backgroundColor: 'rgba(52, 152, 219, 0.1)',
                fill: true,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            animation: false,
            scales: {
                x: {
                    title: { display: true, text: 'Time (hh:mm:ss)' }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Speed (km/h)' }
                }
            }
        }
    });
}

function updateSpeedChart(speed) {
    const now = new Date().toLocaleTimeString();
    const data = speedChart.data;

    data.labels.push(now);
    data.datasets[0].data.push(speed);

    if (data.labels.length > 20) {
        data.labels.shift();
        data.datasets[0].data.shift();
    }

    speedChart.update();
}