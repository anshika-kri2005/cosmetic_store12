// script.js

// Show alert when user clicks "Add to Cart"
document.addEventListener('DOMContentLoaded', function() {
  const addCartButtons = document.querySelectorAll('.add-to-cart-btn');
  
  addCartButtons.forEach(button => {
    button.addEventListener('click', function(event) {
      event.preventDefault(); // prevent default link behavior
      const productName = this.dataset.product;
      alert(`${productName} has been added to your cart!`);
      
      // Optional: update cart count in navbar
      const cartCount = document.getElementById('cart-count');
      if (cartCount) {
        let count = parseInt(cartCount.textContent);
        count += 1;
        cartCount.textContent = count;
      }

      // Redirect to add-to-cart URL
      window.location.href = this.href;
    });
  });
});
