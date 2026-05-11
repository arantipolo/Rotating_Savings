let currentPaymentId = null;   // stores which payment the user is uploading proof for
let currentGroupId = null;  // stores which group is currently opened in the modal
let isGeneratingPayout = false;   // this will ensure that payout generation will only work once.

function setModalStatus(message, type = "success") {
    const status = document.getElementById("modalStatus");

    if (!status) {
        return;
    }

    status.textContent = message;
    status.className = `action-message ${type}`;
    status.hidden = false;
}

// Reads backend JSON safely so server errors do not show as raw HTML parse failures.
async function readJsonResponse(response, fallbackMessage = "Request failed") {
    const responseText = await response.text();
    let data = {};

    try {
        data = responseText ? JSON.parse(responseText) : {};
    } catch (err) {
        throw new Error(fallbackMessage);
    }

    if (!response.ok) {
        throw new Error(data.error || fallbackMessage);
    }

    return data;
}

window.showProofRecipientMessage = function showProofRecipientMessage() {
    setModalStatus("No proof is needed from you for this cycle because you are the payout recipient.", "warning");
}

function syncDashboardCardFromModal(groupId) {
    const currentUserRow = document.querySelector("#modal-body tr[data-current-user-row='true']");
    const dashboardPosition = document.querySelector(`[data-dashboard-position="${groupId}"]`);

    if (!currentUserRow || !dashboardPosition) {
        return;
    }

    const modalPosition = currentUserRow.querySelector("[data-member-position]");

    if (modalPosition) {
        dashboardPosition.textContent = modalPosition.textContent.trim() || "Not assigned";
    }
}

function showConfirmDialog({ title, message, confirmText = "Confirm", danger = true }) {
    let dialog = document.getElementById("confirmDialog");

    if (!dialog) {
        dialog = document.createElement("div");
        dialog.id = "confirmDialog";
        dialog.className = "modal confirm-modal";
        dialog.setAttribute("role", "dialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", "confirmTitle");
        dialog.setAttribute("aria-hidden", "true");
        dialog.innerHTML = `
            <div class="modal-content confirm-dialog">
                <div class="confirm-icon">!</div>
                <h2 id="confirmTitle">Confirm action</h2>
                <p id="confirmMessage">Are you sure?</p>
                <div class="confirm-actions">
                    <button id="confirmCancel" class="btn btn-secondary" type="button">Cancel</button>
                    <button id="confirmAccept" class="btn btn-danger" type="button">Confirm</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);
    }

    const titleElement = document.getElementById("confirmTitle");
    const messageElement = document.getElementById("confirmMessage");
    const cancelButton = document.getElementById("confirmCancel");
    const acceptButton = document.getElementById("confirmAccept");

    if (!dialog || !titleElement || !messageElement || !cancelButton || !acceptButton) {
        console.error("Confirmation dialog is missing from the page.");
        return Promise.resolve(false);
    }

    titleElement.textContent = title;
    messageElement.textContent = message;
    acceptButton.textContent = confirmText;
    acceptButton.className = danger ? "btn btn-danger" : "btn btn-primary";
    dialog.classList.add("active");
    dialog.setAttribute("aria-hidden", "false");

    return new Promise(resolve => {
        function cleanup(result) {
            dialog.classList.remove("active");
            dialog.setAttribute("aria-hidden", "true");
            cancelButton.removeEventListener("click", onCancel);
            acceptButton.removeEventListener("click", onAccept);
            dialog.removeEventListener("click", onBackdrop);
            document.removeEventListener("keydown", onKeydown);
            resolve(result);
        }

        function onCancel() {
            cleanup(false);
        }

        function onAccept() {
            cleanup(true);
        }

        function onBackdrop(event) {
            if (event.target === dialog) {
                cleanup(false);
            }
        }

        function onKeydown(event) {
            if (event.key === "Escape") {
                cleanup(false);
            }
        }

        cancelButton.addEventListener("click", onCancel);
        acceptButton.addEventListener("click", onAccept);
        dialog.addEventListener("click", onBackdrop);
        document.addEventListener("keydown", onKeydown);
        acceptButton.focus();
    });
}

window.openModal = function openModal(groupId, statusMessage = null, statusType = "success") {    // opens modal and run groups from server
    currentGroupId = groupId;    // keep track of active group so we can refresh it later
    console.log("Opening modal:", groupId);

    fetch(`/group_details/${groupId}`)       //  request html content from this group from backend
        .then(response => response.text())   // convert response into plain text
        .then(data => {
            document.getElementById("modal-body").innerHTML = data;  // Put the returned HTML inside the modal body
            document.getElementById("groupModal").classList.add("active");  // display the modal
            syncDashboardCardFromModal(groupId);

            if (statusMessage) {
                setModalStatus(statusMessage, statusType);
            }
        })
        .catch(err => console.error("Error lo ading modal:", err));  //log for debugging
}

// close modal
window.closeModal = function closeModal(){
    // hides the modal by removing active class
    document.getElementById("groupModal").classList.remove("active");
}


// Sends a request to generate payouts for a group
function generatePayouts(groupId) {

    if(isGeneratingPayout) {
        console.log("Payout already in progress...");
        return;
    }

    isGeneratingPayout = true;

    const btn = document.querySelector(`button[onclick="generatePayouts(${groupId})"]`);
    if(btn) {
        btn.disabled = true;
        btn.classList.add("is-loading");
        btn.innerText = "Generating schedule...";
    }

    setModalStatus("Generating payout schedule. This usually only takes a moment.", "loading");

    fetch(`/generate_payouts/${groupId}`, {
        method: "POST"    // POST because we're creating or updating something on the server
    })
        .then(res => readJsonResponse(res, "The server failed while generating the payout schedule."))
        .then(data => {
                //backend sends success flag, if false show error
            if(!data.success){
                setModalStatus(data.error || "Failed to generate payouts.", "danger");
                return;
            }
            console.error("Payout schedule generated");

            openModal(groupId, "Payout schedule generated. The group order is now updated.", "success");  // reload modal so the new data shows up
        })
        .catch(err => {
            console.error("Generate payout error", err);
            setModalStatus("Failed: " + err.message, "danger");
        })
        .finally(() => {
            isGeneratingPayout = false;

            if(btn) {
                btn.disabled = false;
                btn.classList.remove("is-loading");
                btn.innerText = "Generate Payout";
            }
        });
}

//Reset all payouts and payment records for a group
async function resetPayouts(groupId){

    console.log("[RESET] Requesting reset for group: ", groupId);

    const confirmed = await showConfirmDialog({
        title: "Reset payout schedule?",
        message: "This clears the current payout order and payment records for this group.",
        confirmText: "Reset Group",
        danger: false
    });

    if(!confirmed) {
        console.log("[RESET] Cancelled by user");
        return;
    }

    // send reset request to backend
    fetch(`/reset_payouts/${groupId}`, {
        method: "POST"
    })
        .then(res => readJsonResponse(res, "Reset failed"))
        .then(data => {
            console.log("[RESET] Success response:", data);

            if (data.success) {
                isGeneratingPayout= false;
                openModal(groupId, "Payout schedule reset. Positions and proof records are cleared.", "warning");       //reload modal
            } else {
                openModal(groupId, data.error || "Reset failed. Please try again.", "danger");
            }
        })
        .catch(err => {
            console.error("Failed:" + err.message);
            setModalStatus("Failed: " + err.message, "danger");
        });

}

// this function allows the group owner to toggle payout lock or unlock state
function lockPayouts(groupId) {
    const btn = document.querySelector(`button[onclick="lockPayouts(${groupId})"]`);
    const originalText = btn ? btn.innerText : "";

    if (btn) {
        btn.disabled = true;
        btn.classList.add("is-loading");
        btn.innerText = "Updating...";
    }

    setModalStatus("Updating payout lock status.", "loading");

    fetch(`/toggle_lock/${groupId}`, {
        method: "POST"
    })
        .then(res => readJsonResponse(res, "Lock update failed"))
        .then(data => {
            console.log("LOCK RESPONSE:",data);

            // backend returns boolean flag indicating lock state
            if (data.is_payout_locked){
                openModal(groupId, "Payouts locked. The payout order is now protected.", "success");
            } else {
                openModal(groupId, "Payouts unlocked. The group can be adjusted again.", "warning");
            }
        })
        .catch(err => {
            console.error(err);
            setModalStatus("Failed to update payout lock status.", "danger");
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.classList.remove("is-loading");
                btn.innerText = originalText;
            }
        });
}

window.openUploadModal = function (paymentId) {
    console.log("[UPLOAD] Opening panel:", paymentId);

    currentPaymentId = paymentId;
    window.currentPaymentId = paymentId;  // store globally

    const panel = document.getElementById("uploadPanel");
    const fileInput = document.getElementById("proofFile");
    const uploadStatus = document.getElementById("uploadStatus");

    if (!panel) {
        setModalStatus("Upload proof is not available for this payout yet.", "warning");
        return;
    }

    if (fileInput) {
        fileInput.value = "";
    }

    if (uploadStatus) {
        uploadStatus.hidden = true;
        uploadStatus.textContent = "";
    }

    panel.hidden = false;
    panel.scrollIntoView({ behavior: "smooth", block: "center" });
};

// close upload modal
window.closeUploadModal = function () {
    console.log("[UPLOAD] Closing panel");

    const panel = document.getElementById("uploadPanel");
    const fileInput = document.getElementById("proofFile");

    if (panel) {
        panel.hidden = true;
    }

    if (fileInput) {
        fileInput.value = "";
    }

    currentPaymentId = null;
    window.currentPaymentId = null;
}

//submits proof file to backend for the selected payout
window.submitProofUpload = function () {
    const fileInput = document.getElementById("proofFile");
    const uploadStatus = document.getElementById("uploadStatus");

    if (!fileInput || !fileInput.files.length) {
        if (uploadStatus) {
            uploadStatus.textContent = "Choose a receipt or screenshot before submitting.";
            uploadStatus.className = "action-message warning";
            uploadStatus.hidden = false;
        }
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    fetch(`/upload_proof/${window.currentPaymentId}`, {
        method: "POST",
        body: formData
    })
        .then(async (r) => {
            const data = await readJsonResponse(
                r,
                r.status === 413
                    ? "That file is too large. Use a file under 5 MB."
                    : "Upload failed before the server returned proof details."
            );
            console.log(data);

            if (uploadStatus) {
                uploadStatus.textContent = "Proof uploaded. The group details are refreshing.";
                uploadStatus.className = "action-message success";
                uploadStatus.hidden = false;
            }

            closeUploadModal();
            window.openModal(currentGroupId);
        })
        .catch(err => {
            console.error(err);

            if (uploadStatus) {
                uploadStatus.textContent = "Failed: " + err.message;
                uploadStatus.className = "action-message danger";
                uploadStatus.hidden = false;
            } else {
                setModalStatus("Failed: " + err.message, "danger");
            }
        });
};


// Opens a modal to view uploaded proof image
window.viewProof = function(filename){
    const imgWindow = window.open("");

    imgWindow.document.write(`
    <img src="/uploads/${filename}" style="width:100%" alt="Receipt">
`);
}


// Deletes a group after confirming with the user
async function deleteGroup(groupId) {
    const confirmed = await showConfirmDialog({
        title: "Delete this group?",
        message: "This permanently deletes the group, payouts, payment records, and uploaded proof links. This cannot be undone.",
        confirmText: "Delete Group",
        danger: true
    });

    if (!confirmed) {
        return;  //stop if cancel
    }

    fetch(`/delete_group/${groupId}`, {
          method: "POST"
    })
        .then(res => readJsonResponse(res, "Delete failed"))
        .then(data => {
            if(data.success) {
                closeModal();   // close modal after successful  deletion
                const card = document.getElementById(`group-${groupId}`);

                if (card) {
                    card.remove();
                }

                location.reload();  // refresh dashboard after the group is removed
            } else {
                setModalStatus("Delete failed. Please try again.", "danger");
            }
        })
        .catch(err => {
            console.error("Delete error:", err);
            setModalStatus(err.message, "danger");
        });
}
