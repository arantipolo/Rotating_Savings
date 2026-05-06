let currentPaymentId = null;   // stores which payment the user is uploading proof for
let currentGroupId = null;  // stores which group is currently opened in the modal
let isGeneratingPayout = false;   // this will ensure that payout generation will only work once.


window.openModal = function openModal(groupId) {    // opens modal and run groups from server
    currentGroupId = groupId;    // keep track of active group so we can refresh it later
    console.log("Opening modal:", groupId);

    fetch(`/group_details/${groupId}`)       //  request html content from this group from backend
        .then(response => response.text())   // convert response into plain text
        .then(data => {
            document.getElementById("modal-body").innerHTML = data;  // Put the returned HTML inside the modal body
            document.getElementById("groupModal").classList.add("active");  // display the modal
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
        btn.innerText = "Generating...";
    }

    fetch(`/generate_payouts/${groupId}`, {
        method: "POST"    // POST because we're creating or updating something on the server
    })
        .then(res => {
            if(!res.ok) {   // check if backend returned an error status
                return res.json().then(err => {
                    throw new Error(err.error) || "Request failed"
                });
            }
            return  res.json();
        })     // expect JSON back from the server
        .then(data => {
                //backend sends success flag, if false show error
            if(!data.success){
                alert(data.error || "Failed to generate payouts");
                return;
            }
            console.error("Payout schedule generated");
            alert("Payout schedule generated!");

            isGeneratingPayout = true;
            openModal(groupId);  // reload modal so the new data shows up
        })
        .catch(err => {
            console.error("Generate payout error", err);
            alert("Failed: " + err.message);
        })
        .finally(() => {
            isGeneratingPayout = false;

            if(btn) {
                btn.disabled = false;
                btn.innerText = "Generate Payout";
            }
        });
}

//Reset all payouts and payment records for a group
async function resetPayouts(groupId){

    console.log("[RESET] Requesting reset for group: ", groupId);

    // confirm with user before resetting payout
    if(!confirm("This will delete aLL payouts and payment records. Continue?")) {
        console.log("[RESET] Cancelled by user");
        return;
    }

    // send reset request to backend
    fetch(`/reset_payouts/${groupId}`, {
        method: "POST"
    })
        .then(res => {
            console.log("[RESET] Server response status:",res.status);

            // check if reset failed on server side, this will ensure request was successful
            if(!res.ok) {
                return res.json().then(err => {
                    console.log("[RESET] Error response:", err);
                    throw new Error(err.error || "Reset failed");
                });
            }
            return res.json();
        })
        .then(data => {
            console.log("[RESET] Success response:", data);

            if (data.success) {
                alert("Payouts reset successfully");

                isGeneratingPayout= false;
                openModal(groupId);       //reload modal
            } else {
                alert(data.error || "Reset failed!");
                 openModal(groupId);
            }
        })
        .catch(err => {
            console.error("Failed:" + err.message);
            alert("Failed: " + err.message);
        });

}

// this function allows the group owner to toggle payout lock or unlock state
function lockPayouts(groupId) {
    fetch(`/toggle_lock/${groupId}`, {
        method: "POST"
    })
        .then(res => res.json())
        .then(data => {
            console.log("LOCK RESPONSE:",data);

            // backend returns boolean flag indicating lock state
            if (data.is_payout_locked){
                alert("Payouts Locked");
            } else {
                alert("Payouts UNLOCKED");
            }

            openModal(groupId)
        })
        .catch(err => console.error(err));
}

window.openUploadModal = function (paymentId) {
    console.log("Opening modal:", paymentId);

    window.currentPaymentId = paymentId;  // store globally

    document.getElementById("uploadModal").style.display = "block";
};

// close upload modal
window.closeUploadModal = function () {
    console.log("[UPLOAD] Closing modal");

    document.getElementById("uploadModal").style.display = "none";
    currentPaymentId = null;
}

//submits proof file to backend for the selected payout
window.submitProofUpload = function () {
    const fileInput = document.getElementById("proofFile");

    if (!fileInput.files.length) {
        alert("Please select a file");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    fetch(`/upload_proof/${window.currentPaymentId}`, {
        method: "POST",
        body: formData
    })
    //.then(r => r.json())
        .then(async (r) => {
            const data = await r.json();

            if(!r.ok) {
                alert("Failed: " + (data.error || "Upload failed"));
                return;
            }
            console.log(data);
            alert("Uploaded!");
            closeUploadModal();
        })
    .catch(err => console.error(err));
};


// Opens a modal to view uploaded proof image
window.viewProof = function(filename){
    const imgWindow = window.open("");

    imgWindow.document.write(`<img src="/app/uploads/${filename}" style="width:100%" alt="Receipt">`);
}


// Deletes a group after confirming with the user
function deleteGroup(groupId) {
    if (!confirm("Are you sure you want to delete this group? This cannot be undone."))
    {
        return;  //stop if cancel
    }
    fetch(`/delete_group/${groupId}`, {
          method: "POST"
    })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                closeModal();   // close modal after successful  deletion
                alert("Group deleted");

                openModal(groupId)
              //  location.reload();  // refresh dashboard
            }
        })
        .catch(err => console.error("Delete error:", err));
}
