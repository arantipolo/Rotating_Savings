window.openModal = function openModal(groupId) {    // opens modal and run groups from server
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
            closeModal();
        })
        .catch(err => console.error(err));
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

function uploadProof(paymentId) {
    const form = document.getElementById(`uploadForm-${paymentId}`);
    const formData = new FormData(form);

    fetch(`/upload_proof/${paymentId}`, {
        method: "POST",
        body: formData
    })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                alert("Proof uploaded!");
                location.reload();
            } else {
                alert(data.error || "Upload failed");
            }
        })
        .catch(err => console.error(err));
}