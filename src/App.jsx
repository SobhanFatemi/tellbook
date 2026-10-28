import { lazy, Suspense } from "react";
import { Spinner } from "./components/Feedback";
import { Routes, Route } from "react-router-dom";
import BuyerLayout from "./layouts/BuyerLayout";
import AdminLayout from "./layouts/AdminLayout";
import ProtectedRoute from "./routes/ProtectedRoute";
import AdminRoute from "./routes/AdminRoute";

const Products = lazy(() => import("./features/buyer/Products/Products"));
const ProductDetail = lazy(() => import("./features/buyer/Products/Products").then(m => ({ default: m.ProductDetail })));
const Cart = lazy(() => import("./features/buyer/Products/Cart"));
const AdminProducts = lazy(() => import("./features/admin/Products/AdminProducts"));
const Login = lazy(() => import("./features/buyer/Auth/Login"));
const Home = lazy(() => import("./features/buyer/Home/Home"));
const SearchResults = lazy(() => import("./features/buyer/Home/SearchResults"));
const BookDetail = lazy(() => import("./features/buyer/BookDetail/BookDetail"));
const RequestBook = lazy(() => import("./features/buyer/RequestBook/RequestBook"));
const MyRequests = lazy(() => import("./features/buyer/MyRequests/MyRequests"));
const MyOrders = lazy(() => import("./features/buyer/MyOrders/MyOrders"));
const Addresses = lazy(() => import("./features/buyer/Addresses/Addresses"));
const Profile = lazy(() => import("./features/buyer/Profile/Profile"));
const MyShelf = lazy(() => import("./features/buyer/MyShelf/MyShelf"));

const AdminPriceReview = lazy(() => import("./features/admin/PriceReview/AdminPriceReview"));
const AdminCatalog = lazy(() => import("./features/admin/Catalog/AdminCatalog"));
const AdminBookEditor = lazy(() => import("./features/admin/Catalog/AdminBookEditor"));
const AdminPublishers = lazy(() => import("./features/admin/Publishers/AdminPublishers"));
const AdminImports = lazy(() => import("./features/admin/Imports/AdminImports"));
const BookReview = lazy(() => import("./features/admin/BookReview/BookReview"));
const AdminPosts = lazy(() => import("./features/admin/Posts/AdminPosts"));
const AdminDashboard = lazy(() => import("./features/admin/Dashboard/AdminDashboard"));
const AdminRequests = lazy(() => import("./features/admin/Requests/AdminRequests"));
const AdminOrders = lazy(() => import("./features/admin/Orders/AdminOrders"));
const AdminShipments = lazy(() => import("./features/admin/Shipments/AdminShipments"));
const AdminRefunds = lazy(() => import("./features/admin/Refunds/AdminRefunds"));
const AdminDiscounts = lazy(() => import("./features/admin/Discounts/AdminDiscounts"));

const MyShipments = lazy(() => import("./features/buyer/Shipments/MyShipments"));
const StoreSettings = lazy(() => import("./features/admin/Settings/StoreSettings"));

export default function App() {
  return (
    <Suspense fallback={<div role="status" className="flex justify-center gap-3 py-16"><Spinner className="w-5 h-5" />در حال بارگذاری صفحه…</div>}><Routes>
      <Route element={<BuyerLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/products" element={<Products />} />
        <Route path="/products/:id" element={<ProductDetail />} />
        <Route path="/cart" element={<Cart />} />
        <Route path="/search" element={<SearchResults />} />
        <Route path="/books/:id" element={<BookDetail />} />
        <Route path="/shipments" element={<ProtectedRoute><MyShipments /></ProtectedRoute>} />
        <Route path="/login" element={<Login />} />
        <Route path="/request-a-book" element={<RequestBook />} />
        <Route
          path="/requests"
          element={
            <ProtectedRoute>
              <MyRequests />
            </ProtectedRoute>
          }
        />
        <Route
          path="/orders"
          element={
            <ProtectedRoute>
              <MyOrders />
            </ProtectedRoute>
          }
        />
        <Route
          path="/shelf"
          element={
            <ProtectedRoute>
              <MyShelf />
            </ProtectedRoute>
          }
        />
        <Route
          path="/addresses"
          element={
            <ProtectedRoute>
              <Addresses />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route
        path="/admin"
        element={
          <AdminRoute>
            <AdminLayout />
          </AdminRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="products" element={<AdminProducts />} />
        <Route path="prices" element={<AdminPriceReview />} />
          <Route path="books" element={<AdminCatalog />} />
        <Route path="books/:id" element={<AdminBookEditor />} />
        <Route path="publishers" element={<AdminPublishers />} />
        <Route path="imports" element={<AdminImports />} />
        <Route path="imports/:batchId" element={<AdminImports />} />
        <Route path="books/review" element={<BookReview />} />
        <Route path="posts" element={<AdminPosts />} />
        <Route path="requests" element={<AdminRequests />} />
        <Route path="orders" element={<AdminOrders />} />
        <Route path="shipments" element={<AdminShipments />} />
        <Route path="refunds" element={<AdminRefunds />} />
        <Route path="settings" element={<StoreSettings />} />
        <Route path="discounts" element={<AdminDiscounts />} />
      </Route>
    </Routes></Suspense>
  );
}
