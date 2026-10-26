
/* =========================================
   MINDMAP AI - FLASK CONNECTED QUIZ SYSTEM
========================================= */

let currentSubject = "";
let currentQuestionIndex = 0;
let answered = false;
let quizActive = false;
let submitting = false;

let quizQuestions = [];
let currentResults = [];
let selectedAnswers = {};

let csrfToken = "";
let currentScore = 0;
let quizXP = 0;
let demoXP = 0;


/* =========================================
   SAFE JSON RESPONSE HANDLER
========================================= */

async function getJSON(response) {
    const contentType =
        response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
        const text = await response.text();

        console.error(
            "Expected JSON but received:",
            text.slice(0, 500)
        );

        if (response.redirected) {
            throw new Error(
                "Your login session may have expired. " +
                "Please log in again and retry."
            );
        }

        if (response.status === 404) {
            throw new Error(
                "Quiz API route not found. " +
                "Please check your Flask app.py routes."
            );
        }

        if (response.status >= 500) {
            throw new Error(
                "Flask server error. Check the terminal " +
                "where python app.py is running."
            );
        }

        throw new Error(
            "Flask returned HTML instead of JSON. " +
            "Check login and the quiz API route."
        );
    }

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.error || "Request failed."
        );
    }

    return data;
}


/* =========================================
   OPEN QUIZ
========================================= */

async function openQuiz(subject) {
    const quizBox = document.getElementById("quizBox");

    if (!quizBox) {
        alert("Quiz section is missing in index.html.");
        return;
    }

    currentSubject = subject;
    currentQuestionIndex = 0;
    answered = false;
    quizActive = false;
    submitting = false;

    quizQuestions = [];
    currentResults = [];
    selectedAnswers = {};
    currentScore = 0;
    quizXP = 0;

    const questionElement = document.getElementById("question");
    const optionsBox = document.getElementById("options");
    const feedback = document.getElementById("feedback");
    const nextBtn = document.getElementById("nextBtn");

    questionElement.textContent = "Loading your quiz...";
    optionsBox.replaceChildren();
    feedback.textContent = "";
    nextBtn.hidden = true;
    nextBtn.disabled = false;
    nextBtn.onclick = nextQuestion;

    quizBox.hidden = false;

    quizBox.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });

    try {
        const response = await fetch(
            "/api/quiz/questions?subject=" +
            encodeURIComponent(subject),
            {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json"
                }
            }
        );

        const data = await getJSON(response);

        if (!Array.isArray(data.questions) ||
            data.questions.length === 0) {
            throw new Error("No questions available.");
        }

        if (!data.csrf_token) {
            throw new Error(
                "Security token missing. Please refresh."
            );
        }

quizQuestions = data.questions;
csrfToken = data.csrf_token;

quizActive = true;
showQuestion();


    } catch (error) {
        questionElement.textContent = "Quiz could not load.";
        feedback.textContent = error.message;
        optionsBox.replaceChildren();
        nextBtn.hidden = true;

        console.error("Quiz loading error:", error);
    }
}


/* =========================================
   DISPLAY QUESTION
========================================= */

function showQuestion() {
    if (!quizActive) return;

    const q = quizQuestions[currentQuestionIndex];

    const questionElement = document.getElementById("question");
    const optionsBox = document.getElementById("options");
    const feedback = document.getElementById("feedback");
    const nextBtn = document.getElementById("nextBtn");
    const subjectElement = document.getElementById("quizSubject");

    if (!q || !questionElement || !optionsBox ||
        !feedback || !nextBtn || !subjectElement) {
        alert("Some quiz elements are missing in index.html.");
        quizActive = false;
        return;
    }

    answered = false;

    subjectElement.textContent =
        currentSubject.toUpperCase() +
        " CHALLENGE · QUESTION " +
        (currentQuestionIndex + 1) +
        "/" + quizQuestions.length;

    questionElement.textContent = q.question;
    feedback.textContent = "";

    nextBtn.hidden = true;
    nextBtn.disabled = false;

    nextBtn.textContent =
        currentQuestionIndex === quizQuestions.length - 1
            ? "View Results →"
            : "Next Question →";

    nextBtn.onclick = nextQuestion;

    optionsBox.replaceChildren();

    q.options.forEach(option => {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "option-btn";
        button.textContent = option.text;

        button.addEventListener("click", () => {
            checkAnswer(option.id);
        });

        optionsBox.appendChild(button);
    });
}


/* =========================================
   SELECT ANSWER
========================================= */

function checkAnswer(selectedOptionId) {
    if (!quizActive || answered || submitting) return;

    answered = true;

    const q = quizQuestions[currentQuestionIndex];
    selectedAnswers[q.id] = selectedOptionId;

    // Update progress immediately
    updateQuizProgress(
        currentSubject,
        Object.keys(selectedAnswers).length,
        quizQuestions.length
    );

    document.querySelectorAll("#options .option-btn")
        .forEach(function (button) {
            button.disabled = true;
        });

    document.getElementById("feedback").textContent =
        "Answer recorded! Continue to the next question.";

    const nextBtn = document.getElementById("nextBtn");
    nextBtn.hidden = false;
    nextBtn.disabled = false;
}


/* =========================================
   NEXT QUESTION
========================================= */

async function nextQuestion() {
    if (!quizActive || !answered || submitting) return;

    if (currentQuestionIndex < quizQuestions.length - 1) {
        currentQuestionIndex++;
        showQuestion();
        return;
    }

    await submitQuiz();
}


/* =========================================
   SUBMIT QUIZ TO FLASK
========================================= */

async function submitQuiz() {
    if (submitting) return;

    submitting = true;

    const nextBtn = document.getElementById("nextBtn");
    const feedback = document.getElementById("feedback");

    nextBtn.disabled = true;
    nextBtn.textContent = "Saving your result...";

    const answers = quizQuestions.map(q => ({
        question_id: q.id,
        option_id: selectedAnswers[q.id]
    }));

    try {
        const response = await fetch("/api/quiz/submit", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRF-Token": csrfToken
            },
            body: JSON.stringify({
                subject: currentSubject,
                answers: answers
            })
        });

        const data = await getJSON(response);

        currentScore = data.score;
        quizXP = data.score * 10;

        // Retrieve topic-level review
        try {
            const detailResponse = await fetch(
                "/api/quiz/attempt/" + data.attempt_id,
                {
                    credentials: "same-origin",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );

            const detailData = await getJSON(detailResponse);

            currentResults = detailData.responses || [];

        } catch (error) {
            console.warn(
                "Could not load topic review:",
                error
            );
            currentResults = [];
        }

        // Temporary XP display only

demoXP += quizXP;
updateDemoStats();

showResults(data);

// Update progress for the completed quiz
updateQuizProgress(
    currentSubject,
    quizQuestions.length,
    quizQuestions.length
);


    } catch (error) {
        feedback.textContent =
            "Could not save your result: " + error.message;

        nextBtn.disabled = false;
        nextBtn.textContent = "Retry Saving Result";
        nextBtn.onclick = submitQuiz;

        console.error("Quiz submission error:", error);

    } finally {
        submitting = false;
    }
}


/* =========================================
   TEMPORARY DISPLAY STATS
========================================= */

function updateDemoStats() {
    const xpElement = document.getElementById("xp");
    const levelElement = document.getElementById("level");
    const rewardElement = document.getElementById("rewardStatus");

    if (xpElement) {
        xpElement.textContent = demoXP + " XP";
    }

    if (levelElement) {
        levelElement.textContent =
            "Level " + (Math.floor(demoXP / 50) + 1);
    }

    if (rewardElement) {
        rewardElement.textContent =
            demoXP > 0 ? "Unlocked ✨" : "Locked";
    }
}


/* =========================================
   QUIZ RESULTS
========================================= */

function showResults(data) {
    quizActive = false;

    const quizBox = document.getElementById("quizBox");
    const subjectElement = document.getElementById("quizSubject");
    const questionElement = document.getElementById("question");
    const optionsBox = document.getElementById("options");
    const feedback = document.getElementById("feedback");
    const nextBtn = document.getElementById("nextBtn");

    subjectElement.textContent = "QUIZ COMPLETED ✨";

    questionElement.textContent =
        "Your " + (data.subject || currentSubject) + " Results";

    optionsBox.replaceChildren();

    const result = document.createElement("div");
    result.className = "quiz-result";

    const heading = document.createElement("h3");
    heading.textContent =
        data.score + " / " + data.total;

    const percentageText = document.createElement("p");
    percentageText.textContent =
        "Your score: " + data.percentage + "%";

    const xpText = document.createElement("p");
    xpText.textContent =
        "XP earned this quiz: " + quizXP;

    const message = document.createElement("p");

    if (data.percentage >= 80) {
        message.textContent =
            "Amazing work! Keep exploring! 🌟";
    } else if (data.percentage >= 50) {
        message.textContent =
            "Good effort! A little revision will help. 💜";
    } else {
        message.textContent =
            "Keep practicing! Learning takes time. 🌱";
    }

    result.append(
        heading,
        percentageText,
        xpText,
        message
    );

    optionsBox.appendChild(result);

    const topicSummary = document.createElement("div");
    topicSummary.className = "topic-summary";

    const topicHeading = document.createElement("h3");
    topicHeading.textContent = "Your practice review";

    topicSummary.appendChild(topicHeading);

    if (currentResults.length > 0) {
        currentResults.forEach(item => {
            const row = document.createElement("p");

            row.textContent =
                item.topic + ": " +
                (item.is_correct
                    ? "Correct ✓"
                    : "Needs more practice");

            topicSummary.appendChild(row);
        });
    } else {
        const note = document.createElement("p");

        note.textContent =
            "Your saved score is available in quiz history.";

        topicSummary.appendChild(note);
    }

    optionsBox.appendChild(topicSummary);

    feedback.textContent =
        "Your result has been saved to your account.";

    nextBtn.textContent = "Back to Learning";
    nextBtn.hidden = false;
    nextBtn.disabled = false;
    nextBtn.onclick = finishQuiz;

    quizBox.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
}


/* =========================================
   FINISH QUIZ
========================================= */

function finishQuiz() {
    const quizBox = document.getElementById("quizBox");
    const nextBtn = document.getElementById("nextBtn");

    quizBox.hidden = true;

    nextBtn.onclick = nextQuestion;

    const learning = document.getElementById("learning");

    if (learning) {
        learning.scrollIntoView({
            behavior: "smooth"
        });
    }
}

/* =========================================
   UPDATE SUBJECT LEARNING PROGRESS
========================================= */


async function updateSubjectProgress() {
    const subjects = {
        Mathematics: ["Addition", "Multiplication", "Fractions"],
        Science: ["Solar System", "Plants", "Human Body"],
        English: ["Vocabulary", "Grammar"]
    };

    try {
        const response = await fetch("/api/learning-insights", {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json"
            }
        });

        const data = await getJSON(response);
        const topics = Array.isArray(data.topics) ? data.topics : [];

        Object.keys(subjects).forEach(function (subject) {
            const card = document.querySelector(
                '[data-progress-subject="' + subject + '"]'
            );

            if (!card) return;

            const percentElement = card.querySelector(".progress-percent");
            const statusElement = card.querySelector(".progress-status");
            const bar = card.querySelector(".progress-bar-fill");
            const track = card.querySelector(".progress-track");

            const practiced = subjects[subject].filter(function (name) {
                return topics.some(function (item) {
                    return item.topic === name &&
                        Number(item.total) > 0;
                });
            }).length;

            const total = subjects[subject].length;
            const percent = Math.round((practiced / total) * 100);

            if (percentElement) {
                percentElement.textContent = percent + "% completed";
            }

            if (statusElement) {
                statusElement.textContent =
                    practiced + "/" + total + " topics practiced";
            }

            if (bar) {
                bar.style.width = percent + "%";
            }

            if (track) {
                track.setAttribute("aria-valuenow", String(percent));
            }
        });
    } catch (error) {
        console.error("Progress update failed:", error);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    updateSubjectProgress();
});

function updateQuizProgress(subject, answeredCount, totalQuestions) {
    const card = document.querySelector(
        `[data-progress-subject="${subject}"]`
    );

    if (!card) {
        console.warn("Progress card missing:", subject);
        return;
    }

    const percentElement = card.querySelector(".progress-percent");
    const barElement = card.querySelector(".progress-bar-fill");
    const statusElement = card.querySelector(".progress-status");

    const percentage = totalQuestions > 0
        ? Math.round((answeredCount / totalQuestions) * 100)
        : 0;

    if (percentElement) {
        percentElement.textContent = percentage + "% completed";
    }

    if (barElement) {
        barElement.style.width = percentage + "%";
    }

    if (statusElement) {
        statusElement.textContent =
            `${answeredCount}/${totalQuestions} questions answered`;
    }
}
