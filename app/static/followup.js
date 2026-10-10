/* Pure helpers: no requests, bots or automatic sending. */
(function(root){
  const states={pendiente_confirmar:'Pendiente de confirmar',sin_ayuda:'Sin ayuda recibida',parcial:'Ayuda parcial',completa:'Ayuda completa'};
  const message='Hola, le saludamos de ReportaPA. 🇵🇦\n\nEstamos dando seguimiento a su reporte sobre las afectaciones ocasionadas por los sismos.\n\nQueremos saber si su familia ya recibió algún tipo de ayuda.\n\n¿Recibieron ayuda completa, ayuda parcial o todavía no han recibido?\n\nMuchas gracias por su respuesta.';
  function whatsappUrl(raw){
    const value=String(raw||'').trim();
    if(!/^\+?[\d\s().-]+$/.test(value))throw Error('El teléfono registrado no es válido. No se puede abrir WhatsApp.');
    let phone=value.replace(/\D/g,'');
    if(phone.startsWith('507') && (phone.length===10||phone.length===11))phone=phone.slice(3);
    if(!/^(?:[2-5]\d{6}|[2-9]\d{7})$/.test(phone))throw Error('El teléfono registrado no es válido para Panamá. No se puede abrir WhatsApp.');
    return 'https://wa.me/507'+phone+'?text='+encodeURIComponent(message);
  }
  const helpers={states,message,whatsappUrl};
  if(typeof module!=='undefined'&&module.exports)module.exports=helpers;else root.ReportaFollowup=helpers;
})(globalThis);
