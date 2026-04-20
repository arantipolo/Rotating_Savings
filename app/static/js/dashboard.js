window.openModal = function openModal(groupId) {
    console.log("Opening modal:", groupId);

    fetch(`/group_details/${groupId}`)
        .then(response => response.text())
        .then(data => {
            document.getElementById("modal-body").innerHTML = data;
            document.getElementById("groupModal").style.display = "block";
        })
        .catch(err => console.error("Error loading modal:", err));
}

window.closeModal = function closeModal(){
    document.getElementById("groupModal").style.display = "none";
}

function generatePayouts(groupId) {
    fetch(`/generate_payouts/${groupId}`, {
        method: "POST"
    })
        .then(res => res.json())
        .then(data => {
            alert("Payout schedule generated!");

            openModal(groupId)
        })
        .catch(err => console.error(err));
}

function deleteGroup(groupId) {
    if (!confirm("Are you sure you want to delete this group? This cannot be undone."))
    {
        return;
    }
    fetch(`/delete_group/${groupId}`, {
          method: "POST"
    })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                alert("Group deleted");

                closeModal();

                location.reload();  // refresh dashboard
            }
        })
        .catch(err => console.error("Delete error:", err));


}
