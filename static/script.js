const talkButton = document.getElementById("talkButton");
const stopButton = document.getElementById("stopButton");
const talkText = document.getElementById("talkText");

const statusText = document.getElementById("status");
const statusDescription = document.getElementById("statusDescription");

const userText = document.getElementById("userText");
const aiText = document.getElementById("aiText");

let statusInterval = null;

let currentState = "ready";

let micLevel = 0;
let smoothLevel = 0;

let speakingStart = 0;


// ==========================================================
// HELPER
// ==========================================================

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}


// ==========================================================
// ASSISTANT STATE
// ==========================================================

function setAssistantState(state) {

    currentState = state;

    document.body.classList.remove(
        "state-ready",
        "state-listening",
        "state-thinking",
        "state-speaking"
    );

    document.body.classList.add(
        "state-" + state
    );


    // ------------------------------------------------------
    // READY
    // ------------------------------------------------------

    if (state === "ready") {

        statusText.textContent = "READY";

        statusDescription.textContent =
            "Press the button and start speaking";

        talkText.textContent =
            "TALK TO LUMI";

        speakingStart = 0;

        return;
    }


    // ------------------------------------------------------
    // LISTENING
    // ------------------------------------------------------

    if (state === "listening") {

        statusText.textContent =
            "LISTENING";

        statusDescription.textContent =
            "I'm listening to you...";

        talkText.textContent =
            "LISTENING...";

        speakingStart = 0;

        return;
    }


    // ------------------------------------------------------
    // THINKING
    // ------------------------------------------------------

    if (state === "thinking") {

        statusText.textContent =
            "THINKING";

        statusDescription.textContent =
            "LUMI is processing your request...";

        talkText.textContent =
            "THINKING...";

        speakingStart = 0;

        return;
    }


    // ------------------------------------------------------
    // LUMI SPEAKING
    // ------------------------------------------------------

    if (state === "speaking") {

        statusText.textContent =
            "LUMI IS SPEAKING";

        statusDescription.textContent =
            "Listen to LUMI...";

        talkText.textContent =
            "LUMI IS SPEAKING";


        if (!speakingStart) {

            speakingStart =
                performance.now();
        }

        return;
    }
}


// ==========================================================
// FLOWY ORB ANIMATION
// ==========================================================

function updateOrb(now) {

    let targetLevel = 0;

    let pulse = 0;


    // ======================================================
    // IDLE
    // ======================================================

    if (currentState === "ready") {

        /*
            Slow breathing movement.

            The orb is already moving in idle,
            but the movement remains very soft.
        */

        pulse =
            (Math.sin(now / 2200) + 1) / 2;


        targetLevel =
            0.10 +
            pulse * 0.25;
    }


    // ======================================================
    // USER SPEAKING
    // ======================================================

    else if (currentState === "listening") {

        /*
            micLevel comes from Python.

            The orb reacts to your actual
            microphone volume.

            Soft voice  -> small movement
            Normal voice -> medium movement
            Loud voice -> stronger movement
        */

        targetLevel =
            0.06 +
            (micLevel * 0.80);
    }


    // ======================================================
    // THINKING
    // ======================================================

    else if (currentState === "thinking") {

        /*
            Thinking remains calm and subtle.
        */

        pulse =
            (Math.sin(now / 1400) + 1) / 2;


        targetLevel =
            0.08 +
            pulse * 0.14;
    }


    // ======================================================
    // LUMI SPEAKING
    // ======================================================

    else if (currentState === "speaking") {

        /*
            Several slow waves are combined.

            This creates a natural,
            flowy speaking animation instead
            of a sharp pulse.
        */

        const elapsed =
            now - speakingStart;


        const waveOne =
            (Math.sin(elapsed / 500) + 1) / 2;


        const waveTwo =
            (Math.sin(elapsed / 820 + 1.2) + 1) / 2;


        const waveThree =
            (Math.sin(elapsed / 1200 + 2.4) + 1) / 2;


        targetLevel =
            0.14 +
            waveOne * 0.24 +
            waveTwo * 0.11 +
            waveThree * 0.05;
    }


    // ======================================================
    // SMOOTH THE MOVEMENT
    // ======================================================

    /*
        This prevents sudden jumps.

        The lower the number, the smoother
        the animation becomes.
    */

    smoothLevel +=
        (targetLevel - smoothLevel) * 0.10;


    // ======================================================
    // ORB SIZE
    // ======================================================

    /*
        Main orb movement.

        The orb becomes slightly larger
        as the activity increases.
    */

    const scale =
        1 + (smoothLevel * 0.14);


    // ======================================================
    // INNER CORE SIZE
    // ======================================================

    const coreScale =
        1 + (smoothLevel * 0.18);


    // ======================================================
    // SMALL VERTICAL MOVEMENT
    // ======================================================

    const y =
        -(smoothLevel * 3);


    // ======================================================
    // GLOW
    // ======================================================

    const glow =
        clamp(
            smoothLevel,
            0,
            1
        );


    // ======================================================
    // SEND VALUES TO CSS
    // ======================================================

    document.documentElement.style.setProperty(
        "--lumi-scale",
        scale.toFixed(4)
    );


    document.documentElement.style.setProperty(
        "--lumi-core-scale",
        coreScale.toFixed(4)
    );


    document.documentElement.style.setProperty(
        "--lumi-y",
        y.toFixed(2) + "px"
    );


    document.documentElement.style.setProperty(
        "--lumi-glow",
        glow.toFixed(3)
    );


    // Continue animation
    requestAnimationFrame(updateOrb);
}


// ==========================================================
// GET ASSISTANT STATUS FROM PYTHON
// ==========================================================

async function updateAssistantState() {

    try {

        const response =
            await fetch(
                "/assistant_status",
                {
                    cache: "no-store"
                }
            );


        const data =
            await response.json();


        // Update state
        setAssistantState(
            data.state
        );


        // Update microphone level
        micLevel =
            Number(
                data.mic_level || 0
            );

    }

    catch (error) {

        console.log(
            "Status error:",
            error
        );
    }
}


// ==========================================================
// START STATUS MONITORING
// ==========================================================

function startStateMonitoring() {

    if (statusInterval) {

        clearInterval(
            statusInterval
        );
    }


    /*
        Check Python every 50 milliseconds.

        This allows the orb to react
        quickly to your voice.
    */

    statusInterval =
        setInterval(
            updateAssistantState,
            50
        );
}


// ==========================================================
// TALK BUTTON
// ==========================================================

talkButton.addEventListener(
    "click",
    async () => {

        /*
            Don't allow another request while
            LUMI is busy.
        */

        if (currentState !== "ready") {

            return;
        }


        // Disable talk button
        talkButton.disabled = true;

        // Stop button stays disabled while
        // microphone recording is running.
        stopButton.disabled = true;


        // Immediately show listening state
        setAssistantState(
            "listening"
        );


        // --------------------------------------------------
        // RESPONSE LENGTH
        // --------------------------------------------------

        const selected =
            document.querySelector(
                'input[name="responseLength"]:checked'
            );


        const responseLength =
            selected
                ? selected.value
                : "normal";


        try {

            // ------------------------------------------------
            // SEND REQUEST TO FLASK
            // ------------------------------------------------

            const response =
                await fetch(
                    "/ask",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify(
                                {
                                    response_length:
                                        responseLength
                                }
                            )
                    }
                );


            const data =
                await response.json();


            // ------------------------------------------------
            // DISPLAY USER SPEECH
            // ------------------------------------------------

            userText.textContent =
                data.user_text ||
                "No speech detected.";


            // ------------------------------------------------
            // DISPLAY LUMI RESPONSE
            // ------------------------------------------------

            aiText.textContent =
                data.response ||
                "No response.";


            // Get latest backend state
            await updateAssistantState();

        }

        catch (error) {

            console.error(
                "Request error:",
                error
            );


            aiText.textContent =
                "Something went wrong.";


            setAssistantState(
                "ready"
            );
        }
    }
);


// ==========================================================
// STOP BUTTON
// ==========================================================

stopButton.addEventListener(
    "click",
    async () => {

        stopButton.disabled = true;


        try {

            await fetch(
                "/stop",
                {
                    method: "POST"
                }
            );

        }

        catch (error) {

            console.error(
                "Stop error:",
                error
            );
        }


        // --------------------------------------------------
        // RESET VOICE LEVEL
        // --------------------------------------------------

        micLevel = 0;


        // --------------------------------------------------
        // RESET SPEAKING TIMER
        // --------------------------------------------------

        speakingStart = 0;


        // --------------------------------------------------
        // RESET ORB
        // --------------------------------------------------

        smoothLevel = 0;


        // --------------------------------------------------
        // RETURN TO READY
        // --------------------------------------------------

        setAssistantState(
            "ready"
        );


        // --------------------------------------------------
        // RESET BUTTONS
        // --------------------------------------------------

        talkButton.disabled = false;

        stopButton.disabled = true;
    }
);


// ==========================================================
// BUTTON STATE
// ==========================================================

function updateButtonState() {

    // ------------------------------------------------------
    // READY
    // ------------------------------------------------------

    if (currentState === "ready") {

        talkButton.disabled = false;

        stopButton.disabled = true;

        return;
    }


    // ------------------------------------------------------
    // LISTENING
    // ------------------------------------------------------

    if (currentState === "listening") {

        talkButton.disabled = true;

        stopButton.disabled = true;

        return;
    }


    // ------------------------------------------------------
    // THINKING / SPEAKING
    // ------------------------------------------------------

    talkButton.disabled = true;

    stopButton.disabled = false;
}


// Check button state regularly
setInterval(
    updateButtonState,
    100
);


// ==========================================================
// INITIAL SETUP
// ==========================================================

// Start in READY state
setAssistantState(
    "ready"
);


// Start communication with Python
startStateMonitoring();


// Start the orb animation
requestAnimationFrame(
    updateOrb
);