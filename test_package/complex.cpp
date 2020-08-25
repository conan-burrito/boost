#include <boost/filesystem.hpp>
#include <boost/log/trivial.hpp>
#include <boost/range/iterator_range.hpp>

#include <boost/system/error_code.hpp>

#include <boost/asio/io_context.hpp>
#include <boost/asio/buffer.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/steady_timer.hpp>

#include <boost/fiber/future/future.hpp>
#include <boost/fiber/future/promise.hpp>
#include <boost/fiber/mutex.hpp>

#include <boost/fiber/asio/yield.hpp>
#include <boost/fiber/asio/round_robin.hpp>

#include <boost/utility/string_view.hpp>

boost::asio::io_service::id boost::fibers::asio::round_robin::service::id;

using namespace boost::filesystem;

using io_context_t = boost::asio::io_context;
using error_code_t = boost::system::error_code;


class one_shot_timer {
public:
   using timer_t = boost::asio::steady_timer;
   using callback_t = std::function<void()>;
   using duration_t = std::chrono::milliseconds;

   enum class state { waiting, canceled, fired };

public:
   one_shot_timer(io_context_t &io, const duration_t &duration, callback_t func)
      : state_{state::waiting}
      , timer_{io} {
      timer_fiber_ = boost::fibers::fiber([func = std::move(func), duration,
                                           this] {
         timer_.expires_after(duration);

         error_code_t ec;
         timer_.async_wait(boost::fibers::asio::yield[ec]);

         if (state_ == state::canceled || ec == boost::asio::error::operation_aborted) {
            state_ = state::canceled;
            return;
         }

         if (timer_.expires_at() <= timer_t::clock_type::now()) {
            state_ = state::fired;
            func();
         }
      });

      boost::this_fiber::yield();
   }


   ~one_shot_timer() {
      if (timer_fiber_.joinable()) {
         timer_fiber_.join();
      }
   }

private:
   state state_;
   timer_t timer_;
   boost::fibers::fiber timer_fiber_;
};

void test_fiber() {
   auto io_svc = std::make_shared<boost::asio::io_service>();
   boost::fibers::use_scheduling_algorithm<boost::fibers::asio::round_robin>(io_svc);

   one_shot_timer timer{*io_svc, std::chrono::milliseconds{1000}, [&] {
      std::cout << "timer!" << std::endl;
      io_svc->stop();
   }};

   boost::fibers::fiber busy([&] {
      for (int i = 0; i < 20; ++i) {
         std::cout << i << std::endl;
         boost::this_fiber::sleep_for(std::chrono::milliseconds{100});
      }
   });

   std::cout << "starting" << std::endl;
   io_svc->run();
   std::cout << "stopped" << std::endl;

   busy.join();
}

int main(int argc, char *argv[]) {
   path p(argc > 1 ? argv[1] : ".");

   if (is_directory(p)) {
      BOOST_LOG_TRIVIAL(info) << p << " is a directory containing:";

      for (auto &entry : boost::make_iterator_range(directory_iterator(p), {})) {
         BOOST_LOG_TRIVIAL(info) << entry;
      }
   }

   test_fiber();
}
