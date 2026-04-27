let currentPaymentId = null;
let currentGroupId = null;

window.openModal = function openModal(groupId) {    // opens modal and run groups from server
    currentGroupId = groupId;
    console.log("Opening modal:", groupId);

    fetch(`/group_details/${groupId}`)       //  request html content from this group from backend
        .then(response => response.text())   // convert response into plain text
        .then(data => {
            document.getElementById("modal-body").innerHTML = data;  // Put the returned HTML inside the modal body
            document.getElementById("groupModal").style.display = "block";  // display the modal
        })
        .catch(err => console.error("Error loading modal:", err));  //log for debugging
}

// close modal
window.closeModal = function closeModal(){
    document.getElementById("groupModal").style.display = "none";
}

// Sends a request to generate payouts for a group
function generatePayouts(groupId) {
    fetch(`/generate_payouts/${groupId}`, {
        method: "POST"    // POST because we're creating or updating something on the server
    })
        .then(res => res.json())      // expect JSON back from the server
        .then(data => {
            alert("Payout schedule generated!");

            openModal(groupId);  // reload modal so the new data shows up
        })
        .catch(err => console.error(err));
}

// opens upload modal and stores which payout is being uploaded for
window.openUploadModal = function(paymentId, recipientId) {
    console.log("Opening upload modal:", paymentId, recipientId);

    const currentUserId = window.currentUserId;

    //block recipient because recipient should only recieve payment and do not need to upload
    if(Number(currentUserId) === Number(recipientId)){
        alert("This action doesn't apply to you");
        return;
    }
    currentPaymentId = paymentId; // keep track of which payout this upload belongs to
    document.getElementById("uploadModal").style.display = "block";
}

//close the upload modal
window.closeUploadModal = function() {
    document.getElementById("uploadModal").style.display = "none";
    currentPaymentId = null;
}

// submits proof file to backend for the selected payout
window.submitProofUpload = function() {

    console.log("[UPLOAD] submit button clicked!");

    const fileInput = document.getElementById("proofFile");
    const file = fileInput.files[0];

    console.log("[UPLOAD] Selected file:", file);
    // ensure file is seleced
    if (!file) {
        console.warn("[UPLOAD] No file selected");
        alert("Please select a file first");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    // send file to backend
    fetch(`/upload_proof/${currentPaymentId}`, {
        method: "POST",
        body: formData
    })
        .then(res => {
            console.log("[UPLOAD] Server response status:", res.status);
            //ensure that request is successful
            if(!res.ok) {
                return res.text().then(text => {
                    console.error("[UPLOAD] Error response:", text);
                    throw new Error("Upload falied:" + res.status);
                });
            }
            return res.json();
        })
        .then(data => {
            console.log("[UPLOAD] Success response:", data);

            if(data.success) {
                alert("Payment Proof uploaded successfully!");

                //refresh modal so updated proof appears
                openModal(currentGroupId);
                closeUploadModal();
            } else {
                alert(data.error || "Upload falied!");
            }
        })
        .catch(err => {
            console.error("Upload error:", err);
        });
}

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
                closeModal();
                alert("Group deleted");



                location.reload();  // refresh dashboard
            }
        })
        .catch(err => console.error("Delete error:", err));
}
