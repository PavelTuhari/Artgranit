// RO: Serviciul jsReport al platformei Artgranit (localhost:5488).
//     Flask trimite sablonul Handlebars + datele inline la POST /api/report
//     si primeste PDF (recipe chrome-pdf). Studio ramane disponibil pe
//     http://127.0.0.1:5488 pentru editarea/testarea sabloanelor.
// EN: Artgranit's jsReport service (localhost:5488). Flask posts the
//     Handlebars template + data inline to POST /api/report and gets a PDF
//     back (chrome-pdf recipe). Studio stays available on localhost for
//     template editing/testing.
// Config: jsreport.config.json (port, chrome args, single worker — the
// production box has <1GB RAM).
const jsreport = require('jsreport')();

jsreport.init().then(() => {
  console.log('jsreport started on http://127.0.0.1:5488');
}).catch((e) => {
  console.error(e);
  process.exit(1);
});
